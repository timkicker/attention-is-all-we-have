"""Rank candidates on live price and availability with Best Pick.

Keys in order: every hard rule passes, total cost (within 5 % of the cheapest counts as equal),
delivery reliability (no record sorts last), labels the Spend Pass asks for, carbon per kilo.
Each key writes one sentence."""

import math
from datetime import datetime

from ..catalog.model import Product
from ..text.format import and_list, count, product_qty
from ..trust.claims import claim_check
from ..trust.levels import TrustLevel, field_trust, stock_in_sales_units
from ..valio.models import Availability, Quote
from .need import CLAIM_NAMES, Need, Ranked, amount_per_sales_unit, kitchen_break
from .reasons import carbon_sentence, label_sentences, price_sentence, reliability_sentence

TIE_BAND = 0.05

def fmt_time(t: datetime) -> str:
    return f"{t.day} {t:%b %H:%M}"


def rank_one(need: Need, p: Product, q: Quote | None, a: Availability | None, now: datetime) -> Ranked:
    reasons: list[str] = []
    notes: list[str] = []
    open_: list[str] = []
    sales_qty = total = None
    for claim in sorted(need.required_claims):
        level, why = claim_check(p, claim)
        name = CLAIM_NAMES.get(claim, claim)
        if level == TrustLevel.CONTRADICTED:
            reasons.append(f"Not {name}: {and_list(why)}")
        elif level == TrustLevel.MISSING and claim in need.kitchen_claims and (why_not := kitchen_break(p, claim)):
            reasons.append(why_not)
        elif level == TrustLevel.MISSING and claim in need.kitchen_claims:
            # a kitchen-wide diet Valio's data is silent on: not a yes, so Cedar sends it to a person
            open_.append(name)
            notes.append(f"Valio's data doesn't confirm it is {name}")
        elif level == TrustLevel.MISSING:
            reasons.append(f"No {name} claim in Valio's data")
        elif level == TrustLevel.UNCHECKED:
            notes.append(f"{name.capitalize()} claim unchecked: {and_list(why)}")
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
        stock = stock_in_sales_units(p, a)
        if stock is None:
            notes.append("the quantity is unknown")
        elif sales_qty is not None and stock < sales_qty:
            reasons.append(f"Out of stock at Valio, {product_qty(sales_qty, p)} needed" if stock <= 0
                           else f"Only {product_qty(stock, p)} in stock, {count(sales_qty)} needed")
        if a.lines[0].available > need.deliver_by:
            reasons.append(f"Earliest delivery {a.lines[0].available:%d %b}, after {need.deliver_by:%d %b}")
    return Ranked(p, sales_qty, total, not reasons, reasons, notes, field_trust(p, q, a), diet_open=open_)


def best_pick(options: list[Ranked], prefer_labels: tuple[str, ...] = (), band: float = TIE_BAND) -> list[Ranked]:
    """Sort by the five keys and write each option's sentences into `why`. Rejected options keep
    their rejection reasons as sentences and come after every accepted one."""
    ok = {id(r) for r in options if r.accepted and r.total_cents is not None}
    # options whose kitchen diet Valio's data does not confirm come after every confirmed one, priced among
    # themselves, so they never push out an option that may be ordered without a person
    cheapest = {o: min((r.total_cents for r in options if id(r) in ok and bool(r.diet_open) == o), default=0)
                for o in (False, True)}
    prefer = tuple(prefer_labels or ())

    def key(r: Ranked) -> tuple:
        p = r.product
        if id(r) not in ok:
            return (1, r.total_cents is None, r.total_cents or 0, p.id)
        in_band = r.total_cents <= cheapest[bool(r.diet_open)] * (1 + band)
        return (0, bool(r.diet_open), 0 if in_band else r.total_cents, p.reliability is None,
                -(p.reliability or 0), -len(p.labels & set(prefer)), p.carbon_kg_per_kg is None,
                p.carbon_kg_per_kg or 0, r.total_cents, p.id)

    for r in options:
        if id(r) in ok:
            price = price_sentence(r.total_cents, cheapest[bool(r.diet_open)], band)
            if r.diet_open and price == "Cheapest safe option":
                price = "Cheapest option"  # not safe until a person looked at the diet
            r.why = [price, reliability_sentence(r.product), *label_sentences(r.product, prefer),
                     carbon_sentence(r.product)]
            if r.diet_open:
                r.why.append(f"Valio's data doesn't confirm it is {and_list(r.diet_open)}, so you decide")
        else:
            r.why = list(r.reasons) or ["Not usable"]
    return sorted(options, key=key)


def rank(need: Need, cands: list[Product], quotes: dict[str, Quote], avail: dict[str, Availability],
         now: datetime, prefer_labels: tuple[str, ...] = (), band: float = TIE_BAND) -> list[Ranked]:
    out = [rank_one(need, p, quotes.get(p.id), avail.get(p.id), now) for p in cands]
    return best_pick(out, prefer_labels, band)
