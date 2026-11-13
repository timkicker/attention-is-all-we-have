"""Safe Swap: a substitute is only offered if it keeps every diet rule and can be delivered.

Valio's own substitute list comes first, in Valio's order. Only when none of the listed ones passes
does it search the catalog, with at most 8 extra live ids. A substitute outside Valio's list always
goes to a person. Diet checks need no live call, so a blocked substitute costs nothing.
"""

import re
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from enum import StrEnum

from ..catalog.model import Product
from ..catalog.store import Catalog
from ..trust.claims import claim_check
from ..trust.levels import TrustLevel
from ..valio.budget import CallBudget
from ..valio.client import ValioClient
from .need import CLAIM_NAMES, KINDS, Need, Ranked, amount_per_sales_unit, screen
from .rank import best_pick, rank_one

MAX_EXTRA_IDS = 8
ALLERGEN_NAMES = {"AM": "milk", "ML": "lactose", "AW": "gluten cereals", "UW": "wheat"}
CLAIM_ALLERGEN = {"FREE_FROM_LACTOSE": "AM", "FREE_FROM_GLUTEN": "AW"}


class SubVerdict(StrEnum):
    BLOCKED_DIET = "blocked_diet"
    UNDELIVERABLE = "undeliverable"
    REJECTED = "rejected"  # keeps the diet but fails another check (cut-off, stock, pack size)
    OK_LISTED = "ok_listed"
    OUTSIDE_LIST = "candidate_outside_list"


@dataclass
class SubOption:
    product: Product
    verdict: SubVerdict
    sentence: str
    on_valio_list: bool
    ranked: Ranked | None = None  # live check, None when the diet already blocked it


@dataclass
class SwapResult:
    original: Product
    listed: list[SubOption]
    outside: list[SubOption] = field(default_factory=list)
    searched_outside: bool = False
    extra_ids: list[str] = field(default_factory=list)

    @property
    def best(self) -> SubOption | None:
        ok = [o for o in self.listed if o.verdict is SubVerdict.OK_LISTED]
        ok = ok or [o for o in self.outside if o.verdict is SubVerdict.OUTSIDE_LIST]
        return ok[0] if ok else None

    @property
    def needs_person(self) -> bool:
        return self.best is None or not self.best.on_valio_list

    @property
    def sentence(self) -> str:
        b = self.best
        if b is None:
            return "No substitute keeps every rule and can be delivered, so the line waits for a person."
        name = f"{b.product.id} {b.product.name_en}"
        if b.on_valio_list:
            return f"{name} is on Valio's substitute list and keeps every rule."
        return (f"No listed substitute keeps every rule and can be delivered. {name} does, "
                f"but it is not on Valio's list, so a person decides.")


def diet_break(p: Product, claims: set[str]) -> str | None:
    """Why the product breaks the line's diet, or None when it keeps it (unchecked counts as kept here,
    the rule engine sends unchecked claims to a person)."""
    for claim in sorted(claims):
        level, why = claim_check(p, claim)
        name = CLAIM_NAMES.get(claim, claim.lower())
        if level == TrustLevel.CONTRADICTED:
            return f"Not {name}: {'; '.join(why)}"
        if level == TrustLevel.MISSING:
            code = CLAIM_ALLERGEN.get(claim)
            what = name.replace(" ", "-")
            if code and code in p.contains:
                return f"Lists {ALLERGEN_NAMES[code]} and has no {what} claim in Valio's data"
            return f"No {what} claim in Valio's data"
    return None


def _kept(p: Product, claims: set[str]) -> str:
    if not claims:
        return "Keeps the line's rules"
    levels = {claim_check(p, c)[0] for c in claims}
    names = " and ".join(CLAIM_NAMES.get(c, c.lower()) for c in sorted(claims))
    return f"{names.capitalize()} and checked" if levels == {TrustLevel.CONSISTENT} else \
        f"{names.capitalize()}, claim unchecked"


def measured_need(need: Need, original: Product) -> Need:
    """A line in sales units of one product becomes kilos or litres, so packs of another size compare."""
    if need.unit != "PCS":
        return need
    for unit in ("KG", "L"):
        per, _ = amount_per_sales_unit(replace(need, unit=unit), original)
        if per:
            return replace(need, quantity=round(need.quantity * per, 6), unit=unit)
    return need


def _live(opts: list[Product], need: Need, valio: ValioClient, requested: date, budget: CallBudget,
          now: datetime) -> dict[str, Ranked]:
    ids = [p.id for p in opts]
    if not ids:
        return {}
    q, a = valio.price(ids, requested, budget), valio.availability(ids, requested, budget)
    return {p.id: rank_one(need, p, q.get(p.id), a.get(p.id), now) for p in opts}


def blend_note(p: Product, need: Need) -> str | None:
    """A name like "mozzarella-fontal" or "Edam-Emmental-Mozzarella" is a blend with another cheese."""
    for w in (KINDS[need.kind].words if need.kind in KINDS else ()):
        m = re.search(rf"\b(?:\w+-)+{w}\b|\b{w}(?:-\w+)+", p.name_en or "", re.IGNORECASE)
        if m:
            return f"A {m.group(0).lower()} blend, not pure {w}"
    return None


def _judge(p: Product, r: Ranked, need: Need, listed: bool) -> SubOption:
    kept = _kept(p, need.required_claims)
    if r.accepted and (blend := blend_note(p, need)):
        kept = f"{kept}. {blend}"
        r.notes.append(blend)
    if "Valio gives no delivery date for it" in r.reasons:
        return SubOption(p, SubVerdict.UNDELIVERABLE, f"{kept}, but Valio gives no delivery date for it", listed, r)
    if not r.accepted:
        return SubOption(p, SubVerdict.REJECTED, "; ".join(r.reasons), listed, r)
    qty = f"{r.sales_qty} {p.sales_unit} for {r.total_cents / 100:.2f} EUR"
    if listed:
        return SubOption(p, SubVerdict.OK_LISTED, f"{kept}. {qty}, on Valio's substitute list", True, r)
    return SubOption(p, SubVerdict.OUTSIDE_LIST, f"{kept}. {qty}, not on Valio's list", False, r)


def safe_swap(original: Product, need: Need, cat: Catalog, valio: ValioClient, requested: date,
              budget: CallBudget, now: datetime, search_outside: bool = True) -> SwapResult:
    need = measured_need(need, original)
    listed_products = cat.substitutes_of(original.id)
    blocked = {p.id: diet_break(p, need.required_claims) for p in listed_products}
    live = _live([p for p in listed_products if blocked[p.id] is None], need, valio, requested, budget, now)
    listed = [SubOption(p, SubVerdict.BLOCKED_DIET, blocked[p.id], True) if blocked[p.id]
              else _judge(p, live[p.id], need, True) for p in listed_products]
    result = SwapResult(original, listed)
    if result.best or not search_outside:
        return result

    result.searched_outside = True
    skip = {original.id, *blocked}
    wide = replace(need, product_id=None)
    kept, _ = screen(wide, cat, limit=None)
    extra = [p for p in kept if p.id not in skip and diet_break(p, need.required_claims) is None][:MAX_EXTRA_IDS]
    result.extra_ids = [p.id for p in extra]
    live = _live(extra, need, valio, requested, budget, now)
    ranked = best_pick(list(live.values()))
    result.outside = [_judge(r.product, r, need, False) for r in ranked]
    return result

