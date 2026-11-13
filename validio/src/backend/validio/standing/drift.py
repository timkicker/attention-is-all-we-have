"""Drift Watch: before each renewal, look for four things that make the usual order wrong this week.

per guest up    the last 2 weeks are more than 20 % over the first 4, per guest
cost up         this week's line cost is more than 10 % over the median of the past weeks
contract ends   the price ends before the next 4 renewals
stock below     Valio has less in stock than the usual line

Only Valio's answers and the kitchen's own history count. Supplier text never does."""

from datetime import date, datetime, timedelta
from statistics import mean, median

from ..audit.sentences import eur
from ..catalog.store import Catalog
from ..text.format import count
from ..text.format import unit_word as fmt_unit_word
from ..trust.levels import stock_in_sales_units
from ..valio.models import Availability, Quote
from .model import DriftFlag, DriftKind, History, StandingOrder

PER_GUEST_UP = 0.20
COST_UP = 0.10
RENEWALS_AHEAD = 4
FIRST_WEEKS, LAST_WEEKS = 4, 2
def unit_word(a: Availability | None, sales_unit: str | None = None) -> str:
    """The word for the product's sales unit when given, else for the unit Valio answered in (plural)."""
    unit = sales_unit or (a.lines[0].sales_unit if a is not None and a.lines else "")
    return fmt_unit_word(unit) or "units"


def day(d: date) -> str:
    return f"{d.day} {d:%b}"


def next_renewals(weekday: int, now: datetime, n: int = RENEWALS_AHEAD) -> list[date]:
    today = now.date()
    first = today + timedelta(days=(weekday - today.weekday()) % 7 or 7)
    return [first + timedelta(weeks=i) for i in range(n)]


def _num(x: float) -> str:
    return f"{x:g}" if x == int(x) else f"{x:.1f}"


def _per_guest(so: StandingOrder, history: History, avail: dict[str, Availability]) -> list[DriftFlag]:
    weeks = sorted(history.weeks, key=lambda w: w.delivered)
    if len(weeks) < FIRST_WEEKS + LAST_WEEKS:
        return []
    first, last = weeks[:FIRST_WEEKS], weeks[-LAST_WEEKS:]
    out = []
    for ln in so.lines:
        before = mean(w.qty(ln.product_id) / w.guests for w in first)
        now = mean(w.qty(ln.product_id) / w.guests for w in last)
        if before <= 0 or now <= before * (1 + PER_GUEST_UP):
            continue
        ratio = now / before
        pct = round((ratio - 1) * 100)
        guests = {w.guests for w in first + last}
        who = f"with {guests.pop()} guests every week" if len(guests) == 1 else "counted per guest"
        unit = unit_word(avail.get(ln.product_id))
        a_first = mean(w.qty(ln.product_id) for w in first)
        a_last = mean(w.qty(ln.product_id) for w in last)
        out.append(DriftFlag(
            DriftKind.PER_GUEST_UP, ln.product_id,
            f"The last {LAST_WEEKS} weeks averaged {_num(a_last)} {unit}, the first {FIRST_WEEKS} averaged "
            f"{_num(a_first)}, {who}. That is {pct} % more per guest ({before:.2f} to {now:.2f} {unit} per guest). "
            "Renew anyway?",
            round(ratio, 4), pct))
    return out


def _cost(so: StandingOrder, history: History, quotes: dict[str, Quote],
          avail: dict[str, Availability]) -> list[DriftFlag]:
    out = []
    for ln in so.lines:
        q = quotes.get(ln.product_id)
        if q is None or q.error or q.price_cents is None or not history.weeks:
            continue
        this_week = ln.sales_qty * q.price_cents
        # a week without a recorded price counts as paid at today's price (flat simulated history)
        past = median(w.qty(ln.product_id) * w.unit_cents.get(ln.product_id, q.price_cents) for w in history.weeks)
        if past <= 0 or this_week <= past * (1 + COST_UP):
            continue
        pct = round((this_week / past - 1) * 100)
        out.append(DriftFlag(
            DriftKind.COST_UP, ln.product_id,
            f"This week the line costs {eur(this_week)}, {pct} % over its usual {eur(round(past))}.",
            this_week, pct))
    return out


def _contract(so: StandingOrder, quotes: dict[str, Quote], now: datetime) -> list[DriftFlag]:
    last = next_renewals(so.weekday, now)[-1]
    out = []
    for ln in so.lines:
        q = quotes.get(ln.product_id)
        if q is None or q.error or q.valid_to is None or q.valid_to >= last:
            continue
        price = eur(q.price_cents) if q.price_cents is not None else "the contract price"
        out.append(DriftFlag(
            DriftKind.CONTRACT_ENDS, ln.product_id,
            f"The price of {price} ends {day(q.valid_to)}, before the {RENEWALS_AHEAD}th renewal on {day(last)}.",
            (last - q.valid_to).days))
    return out


def _stock(so: StandingOrder, avail: dict[str, Availability], cat: Catalog) -> list[DriftFlag]:
    """Stock in the product's sales unit. A count that is not real or cannot be converted raises no flag here:
    the Hard Lines then find that the stock does not cover the line, and it waits for a person."""
    out = []
    for ln in so.lines:
        a, p = avail.get(ln.product_id), cat.get(ln.product_id)
        unit = unit_word(a, p.sales_unit if p else None)
        stock = stock_in_sales_units(p, a) if p is not None else None
        if a is None or not a.deliverable:
            out.append(DriftFlag(DriftKind.STOCK_BELOW, ln.product_id,
                                 f"Valio gives no delivery date for it, the usual line is {count(ln.sales_qty)} {unit}.", 0))
        elif stock is not None and stock <= 0:
            out.append(DriftFlag(DriftKind.STOCK_BELOW, ln.product_id,
                                 f"Out of stock at Valio, the usual line is {count(ln.sales_qty)} {unit}.", stock))
        elif stock is not None and stock < ln.sales_qty:
            out.append(DriftFlag(DriftKind.STOCK_BELOW, ln.product_id,
                                 f"Only {count(stock)} {unit} in stock, the usual line is {count(ln.sales_qty)}.",
                                 stock))
    return out


def detect(so: StandingOrder, history: History, quotes: dict[str, Quote], avail: dict[str, Availability],
           now: datetime, cat: Catalog) -> list[DriftFlag]:
    flags = _per_guest(so, history, avail) + _cost(so, history, quotes, avail) + _contract(so, quotes, now) \
        + _stock(so, avail, cat)
    order = {ln.product_id: i for i, ln in enumerate(so.lines)}
    return sorted(flags, key=lambda f: order.get(f.product_id, len(order)))
