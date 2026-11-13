"""Rank candidates on live price and availability. Price only for now, Best Pick comes later."""

import math
from datetime import datetime

from ..catalog.model import Product
from ..trust.claims import claim_check
from ..trust.levels import TrustLevel, field_trust
from ..valio.models import Availability, Quote
from .need import CLAIM_NAMES, Need, Ranked, amount_per_sales_unit

UNKNOWN_AMOUNT = 999999


def fmt_time(t: datetime) -> str:
    return f"{t.day} {t:%b %H:%M}"


def quantity_unknown(a: Availability) -> bool:
    return a.logistic_model == "Terminal" or a.amount == UNKNOWN_AMOUNT


def rank_one(need: Need, p: Product, q: Quote | None, a: Availability | None, now: datetime) -> Ranked:
    reasons: list[str] = []
    notes: list[str] = []
    sales_qty = total = None
    for claim in sorted(need.required_claims):
        level, why = claim_check(p, claim)
        name = CLAIM_NAMES.get(claim, claim)
        if level == TrustLevel.CONTRADICTED:
            reasons.append(f"Not {name}: {'; '.join(why)}")
        elif level == TrustLevel.MISSING:
            reasons.append(f"No {name} claim in Valio's data")
        elif level == TrustLevel.UNCHECKED:
            notes.append(f"{name.capitalize()} claim unchecked: {'; '.join(why)}")
    if q is None or q.error or q.price_cents is None:
        reasons.append("Valio has no price for it")
    per, note = amount_per_sales_unit(need, p, q)
    if per is None:
        reasons.append(f"Pack size unknown ({note})")
    else:
        sales_qty = math.ceil(round(need.quantity / per, 6))
        if q and q.price_cents is not None:
            total = sales_qty * q.price_cents
    if a is None or not a.deliverable:
        reasons.append("Valio gives no delivery date for it")
    else:
        if a.closing_time and a.closing_time < now:
            reasons.append(f"Order cut-off {fmt_time(a.closing_time)} has passed")
        if quantity_unknown(a):
            notes.append("the quantity is unknown")
        elif sales_qty is not None and a.amount < sales_qty:
            reasons.append(f"Only {a.amount:g} {a.lines[0].sales_unit} in stock, {sales_qty} needed")
        if a.lines[0].available > need.deliver_by:
            reasons.append(f"Earliest delivery {a.lines[0].available:%d %b}, after {need.deliver_by:%d %b}")
    return Ranked(p, sales_qty, total, not reasons, reasons, notes, field_trust(p, q, a))


def rank(need: Need, cands: list[Product], quotes: dict[str, Quote],
         avail: dict[str, Availability], now: datetime) -> list[Ranked]:
    out = [rank_one(need, p, quotes.get(p.id), avail.get(p.id), now) for p in cands]
    return sorted(out, key=lambda r: (not r.accepted, r.total_cents is None, r.total_cents or 0, r.product.id))
