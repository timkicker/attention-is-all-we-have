"""Renew a Steady Order. Lines without a flag go through the normal pipeline (Fact Grades, Hard Lines).
A line short on stock goes to Split Fill and renews alone only when the split keeps every rule.
Lines Drift Watch flagged wait for a person.

The Spend Pass gives the money limits. The diet rule applies per line: each line carries its own required
claims (mozzarella lactose free, pancakes gluten free and vegan, parmesan none).
"""

import math
from collections.abc import Callable
from dataclasses import replace
from datetime import date, datetime

from ..audit.sentences import eur
from ..catalog.store import Catalog
from ..matching.split import SplitPlan, decide_split, plan_split
from ..policy.decide import Outcome, context_for, decide
from ..policy.mandate import Mandate
from ..trust.levels import stock_in_sales_units
from ..valio.budget import CallBudget
from ..valio.client import ValioClient
from ..valio.models import Availability, Quote
from .drift import detect, next_renewals, unit_word
from .model import (
    DriftFlag,
    DriftKind,
    History,
    LineResult,
    Renewal,
    RenewedLine,
    StandingLine,
    StandingOrder,
)

MAX_IDS = 40
SplitFill = Callable[..., SplitPlan | None]  # plan_split(first, wanted, required_claims, cat, quotes, avail, bp)


def fetch(so: StandingOrder, cat: Catalog, valio: ValioClient, now: datetime, stockout: bool,
          max_ids: int = MAX_IDS) -> tuple[dict[str, Quote], dict[str, Availability], CallBudget]:
    """Price and availability for every line and its listed substitutes, for the next delivery day."""
    from ..demo.seed import apply_stockout

    ids: list[str] = []
    for ln in so.lines:
        ids.append(ln.product_id)
        p = cat.get(ln.product_id)
        ids.extend(p.substitutes if p else ())
    ids = list(dict.fromkeys(ids))
    budget = CallBudget(max_ids)
    day = next_renewals(so.weekday, now, 1)[0]
    quotes = valio.price(ids, day, budget)
    avail = apply_stockout(valio.availability(ids, day, budget), on=stockout)
    return quotes, avail, budget


def _line(ln: StandingLine, flags: list[DriftFlag], cat: Catalog, quotes: dict[str, Quote],
          avail: dict[str, Availability], mandate: Mandate, now: datetime, split_fill: SplitFill,
          delivery: date | None = None) -> RenewedLine:
    pid, usual = ln.product_id, ln.sales_qty
    p, q, a = cat.get(pid), quotes.get(pid), avail.get(pid)
    unit = unit_word(a, p.sales_unit if p else None)
    price = None if q is None or q.error else q.price_cents
    base = RenewedLine(pid, usual, None, None, LineResult.WAITING, "", flags)
    if p is None or price is None:
        return replace(base, sentence="Valio has no price for it this week, so it waits for you.")
    total = usual * price
    drift = [f for f in flags if f.kind is not DriftKind.STOCK_BELOW]
    short = [f for f in flags if f.kind is DriftKind.STOCK_BELOW]

    if drift:
        d = decide(context_for(mandate, p, a, total_cents=total, now=now, is_renewal=True, drift_flag=True,
                               required_claims=ln.diet, sales_qty=usual, deliver_by=delivery), pid)
        if d.outcome is Outcome.DENY:
            return replace(base, this_week_qty=usual, total_cents=total, result=LineResult.BLOCKED,
                           sentence=d.sentence, decision=d)
        return replace(base, this_week_qty=usual, total_cents=total, result=LineResult.FLAGGED,
                       sentence="Waits for you because of the flag below.", decision=d,
                       accept_label="Renew anyway")

    if short:
        plan = split_fill(p, usual, set(ln.diet), cat, quotes, avail, mandate.split_max_extra_bp)
        if plan is None or not plan.parts:
            stock = stock_in_sales_units(p, a)
            have = min(usual, math.floor(round(stock, 6))) if stock else 0
            return replace(base, this_week_qty=have or None, split=plan,
                           sentence=short[0].sentence + " No split keeps every rule, so it waits for you.",
                           accept_label=f"Order {have} now" if have else None)
        got = sum(x.sales_qty for x in plan.parts)
        if plan.needs_person:
            head = plan.parts[0].sales_qty if plan.parts[0].product.id == pid else 0
            why = ". ".join(b.rstrip(".") for b in plan.breaks) or "No listed substitute can fill the rest"
            return replace(base, this_week_qty=got, total_cents=plan.total_cents, split=plan,
                           sentence=f"{head} of {usual} {unit} can come. {why}. Order {got} now?",
                           accept_label=f"Order {got} now")
        d = decide_split(plan, mandate, now, required_claims=ln.diet, deliver_by=delivery)
        if d.outcome is Outcome.ALLOW:
            extra = plan.total_cents - plan.base_cents
            added = " plus ".join(f"{x.sales_qty} of {x.product.id}" for x in plan.parts if x.on_valio_list)
            limit = f"{mandate.split_max_extra_bp / 100:g}"
            return replace(base, this_week_qty=got, total_cents=plan.total_cents, result=LineResult.SPLIT_RENEWED,
                           split=plan, decision=d,
                           sentence=f"{short[0].sentence} So {added} come from Valio's own substitute list. "
                                    f"{eur(extra)} ({plan.extra_pct} %) more, inside your {limit} % split limit.")
        result = LineResult.BLOCKED if d.outcome is Outcome.DENY else LineResult.WAITING
        return replace(base, this_week_qty=got, total_cents=plan.total_cents, result=result, split=plan,
                       decision=d, sentence=d.sentence,
                       accept_label=None if result is LineResult.BLOCKED else "Order the split")

    d = decide(context_for(mandate, p, a, total_cents=total, now=now, is_renewal=True,
                           required_claims=ln.diet, sales_qty=usual, deliver_by=delivery), pid)
    if d.outcome is Outcome.ALLOW:
        return replace(base, this_week_qty=usual, total_cents=total, result=LineResult.RENEWED,
                       sentence="Same as usual.", decision=d)
    result = LineResult.BLOCKED if d.outcome is Outcome.DENY else LineResult.WAITING
    return replace(base, this_week_qty=usual, total_cents=total, result=result, sentence=d.sentence, decision=d,
                   accept_label=None if result is LineResult.BLOCKED else "Renew anyway")


def renew(so: StandingOrder, flags: list[DriftFlag], cat: Catalog, quotes: dict[str, Quote],
          avail: dict[str, Availability], mandate: Mandate, now: datetime, split_fill: SplitFill = plan_split) -> Renewal:
    delivery = next_renewals(so.weekday, now, 1)[0]
    lines = [_line(ln, [f for f in flags if f.product_id == ln.product_id], cat, quotes, avail, mandate, now,
                   split_fill, delivery) for ln in so.lines]
    return Renewal(so.id, now, delivery, lines, so.simulated)


def run(so: StandingOrder, history: History, cat: Catalog, valio: ValioClient, mandate: Mandate, now: datetime,
        stockout: bool, split_fill: SplitFill = plan_split) -> Renewal:
    quotes, avail, _ = fetch(so, cat, valio, now, stockout)
    return renew(so, detect(so, history, quotes, avail, now, cat), cat, quotes, avail, mandate, now, split_fill)


def accept(renewal: Renewal, product_id: str, approver: str) -> Renewal:
    """A person lets a waiting or flagged line through. A blocked line stays blocked."""
    lines = []
    for ln in renewal.lines:
        if ln.product_id == product_id:
            if ln.result not in (LineResult.WAITING, LineResult.FLAGGED):
                raise ValueError(f"line {product_id} is {ln.result}, only a waiting or flagged line can be accepted")
            ln = replace(ln, result=LineResult.ACCEPTED, accept_label=None, accepted_by=approver)
        lines.append(ln)
    if lines == renewal.lines:
        raise ValueError(f"no line {product_id} in {renewal.order_id}")
    return replace(renewal, lines=lines)
