"""Split Fill: when stock is short, take the ordered product up to its attested stock, then add
Valio's listed substitutes in Valio's order.

Each part must keep the line's diet, come from Stock with a real number and keep the extra cost
within the Spend Pass split limit. Pack sizes convert by weight or volume. A part that would break
a rule is never added: it lands in `breaks` and the line waits for a person.
"""

import math
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime

from ..catalog.model import Product
from ..catalog.store import Catalog
from ..policy.decide import Decision, Outcome, Policy, context_for, decide
from ..policy.mandate import Mandate
from ..trust.levels import stock_in_sales_units
from ..valio.budget import CallBudget
from ..valio.client import ValioClient
from ..valio.models import Availability, Quote
from .need import kg_per_sales_unit, litres_per_sales_unit
from .reasons import eur
from .substitute import diet_break


@dataclass
class SplitPart:
    product: Product
    sales_qty: int
    total_cents: int
    on_valio_list: bool  # True for listed substitutes, False for the ordered product itself
    availability: Availability


@dataclass
class SplitPlan:
    first: Product
    wanted: int  # sales units of the ordered product
    base_cents: int  # what the wanted amount of the ordered product would cost
    max_extra_bp: int
    parts: list[SplitPart] = field(default_factory=list)
    covered: float = 0.0  # share of the wanted amount the parts cover
    refused: list[tuple[Product, str]] = field(default_factory=list)  # would break a rule
    skipped: list[tuple[Product, str]] = field(default_factory=list)  # cannot be delivered

    @property
    def total_cents(self) -> int:
        return sum(p.total_cents for p in self.parts)

    @property
    def extra_bp(self) -> int:
        return max(0, math.ceil((self.total_cents - self.base_cents) * 10000 / self.base_cents))

    @property
    def extra_pct(self) -> str:
        return f"{(self.total_cents - self.base_cents) * 100 / self.base_cents:.1f}"

    @property
    def breaks(self) -> list[str]:
        return [f"{p.id} {p.name_en} would break a rule: {why}" for p, why in self.refused]

    @property
    def complete(self) -> bool:
        return self.covered >= 1 - 1e-9

    @property
    def needs_person(self) -> bool:
        return bool(self.refused) or not self.complete

    @property
    def sentence(self) -> str:
        unit = self.first.sales_unit
        if not self.complete:
            head = self.parts[0].sales_qty if self.parts else 0
            s = f"{head} of {self.wanted} {unit} can come."
            if self.breaks:
                s += " " + ". ".join(self.breaks) + ". The rest waits for you"
            else:
                s += " No listed substitute can fill the rest. It waits for you"
            return s
        parts = " plus ".join(
            f"{p.sales_qty} {p.product.sales_unit} of {p.product.id}" for p in self.parts)
        diff = self.total_cents - self.base_cents
        limit = f"{self.max_extra_bp / 100:g} %"
        return (f"{parts} from Valio's own substitute list for {eur(self.total_cents)}. "
                f"{eur(diff)} ({self.extra_pct} %) more, inside your {limit} split limit")


def _stock(p: Product, a: Availability | None) -> int | None:
    """Attested stock in whole sales units, None when Valio does not confirm a real number in a known unit."""
    if a is None or a.logistic_model != "Stock":
        return None
    stock = stock_in_sales_units(p, a)
    return None if stock is None else math.floor(round(stock, 6))


def _measure(p: Product, q: Quote | None, unit: str) -> float | None:
    return (kg_per_sales_unit if unit == "KG" else litres_per_sales_unit)(p, q)[0]


def plan_split(first: Product, wanted: int, required_claims: set[str], cat: Catalog,
               quotes: dict[str, Quote], avail: dict[str, Availability],
               max_extra_bp: int = 500) -> SplitPlan | None:
    """None when the ordered product covers the line alone or cannot be priced."""
    q0, a0 = quotes.get(first.id), avail.get(first.id)
    stock0 = _stock(first, a0)
    if q0 is None or q0.price_cents is None or stock0 is None or stock0 >= wanted:
        return None
    plan = SplitPlan(first, wanted, wanted * q0.price_cents, max_extra_bp)
    if stock0 > 0:
        plan.parts.append(SplitPart(first, stock0, stock0 * q0.price_cents, False, a0))
    unit = next((u for u in ("KG", "L") if _measure(first, q0, u)), None)
    per0 = _measure(first, q0, unit) if unit else None
    short = float(wanted - stock0)  # in sales units of the ordered product
    for sub in cat.substitutes_of(first.id):
        if short <= 1e-9:
            break
        q, a = quotes.get(sub.id), avail.get(sub.id)
        if a is None or not a.deliverable:
            plan.skipped.append((sub, "Valio gives no delivery date for it"))
            continue
        why = [w for w in [diet_break(sub, required_claims)] if w]
        stock = _stock(sub, a)
        if stock is None:
            why.append(f"Valio does not confirm its stock ({a.logistic_model})")
        if q is None or q.price_cents is None:
            why.append("Valio has no price for it")
        per = _measure(sub, q, unit) if unit else None
        if not why and (per0 is None or per is None):
            why.append("pack sizes cannot be converted by weight or volume")
        if why:
            plan.refused.append((sub, "; ".join(why)))
            continue
        qty = min(stock, math.ceil(round(short * per0 / per, 6)))
        part = SplitPart(sub, qty, qty * q.price_cents, True, a)
        after = plan.total_cents + part.total_cents
        if (after - plan.base_cents) * 10000 > max_extra_bp * plan.base_cents:
            pct = (after - plan.base_cents) * 100 / plan.base_cents
            why_cost = f"the split would cost {pct:.1f} % more, over your {max_extra_bp / 100:g} % split limit"
            plan.refused.append((sub, why_cost))
            continue
        plan.parts.append(part)
        short = max(0.0, short - qty * per / per0)
    plan.covered = min(1.0, (wanted - short) / wanted)
    return plan


def split_fill(first: Product, wanted: int, required_claims: set[str], cat: Catalog, valio: ValioClient,
               requested: date, budget: CallBudget, max_extra_bp: int = 500) -> SplitPlan | None:
    """Ask Valio about the ordered product and its listed substitutes, then plan the split."""
    ids = [first.id, *first.substitutes]
    quotes, avail = valio.price(ids, requested, budget), valio.availability(ids, requested, budget)
    return plan_split(first, wanted, required_claims, cat, quotes, avail, max_extra_bp)


_WORST = {Outcome.ALLOW: 0, Outcome.ESCALATE: 1, Outcome.DENY: 2}


def decide_split(plan: SplitPlan, mandate: Mandate, now: datetime, policy: Policy | None = None,
                 required_claims: Iterable[str] | None = None, deliver_by: date | None = None) -> Decision:
    """Hard Lines for a complete split: Cedar judges every part with the split's total, the worst
    outcome wins. A split that falls short or refused a part always waits for a person and is not
    sent here. `required_claims` is the line's own diet, None means the Spend Pass diet."""
    if plan.needs_person:
        raise ValueError("an incomplete split or one with a refused part waits for a person")
    worst = None
    for part in plan.parts:
        ctx = context_for(mandate, part.product, part.availability, total_cents=plan.total_cents, now=now,
                          is_substitute=part.on_valio_list, on_valio_list=part.on_valio_list,
                          split_base_cents=plan.base_cents, required_claims=required_claims,
                          sales_qty=part.sales_qty, deliver_by=deliver_by)
        d = decide(ctx, part.product.id, policy=policy)
        if worst is None or _WORST[d.outcome] > _WORST[worst.outcome]:
            worst = d
    return worst
