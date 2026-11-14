"""The comparison rows of one option, in plain words: price per litre or kilo, when it arrives, the order
cut-off, how often Valio delivered it in full and how sure the diet is. Plus why the chosen one won and why
each other one did not, from the same Best Pick keys rank.py sorts by. Only reads what Valio already
answered and the static catalog: no extra call."""

from datetime import datetime

from ..catalog.model import Product
from ..text.format import money
from ..trust.claims import claim_check
from ..valio.models import Availability, Quote
from .need import CLAIM_NAMES, Need, Ranked, amount_per_sales_unit
from .rank import TIE_BAND

GRADE_WORDS = {"attested": "Valio confirms", "attested_until": "Valio confirms",
               "consistent": "Valio confirms, ingredients agree", "unchecked": "Not confirmed, you decide",
               "contradicted": "Ingredients say otherwise", "missing": "No data from Valio",
               "unknown": "No data from Valio", "untrusted": "Supplier's own words"}


def _day(d) -> str:
    return f"{d:%a} {d.day} {d:%b}"


def unit_price_cents(need: Need, r: Ranked, q: Quote | None) -> float | None:
    """Cents per litre or kilo of what this option costs for the request, None for pieces or an unknown pack."""
    if need.unit not in ("L", "KG") or not r.total_cents or not r.sales_qty:
        return None
    per, _ = amount_per_sales_unit(need, r.product, q)
    return r.total_cents / (r.sales_qty * per) if per else None


def unit_price_text(cents: float | None, unit: str) -> str | None:
    if cents is None:
        return None
    return f"{money(round(cents))} per {'l' if unit == 'L' else 'kg'}"


def delivery_text(a: Availability | None) -> str | None:
    return f"Arrives {_day(a.lines[0].available)}" if a is not None and a.lines else None


def cutoff_text(a: Availability | None, now: datetime) -> str | None:
    if a is None or a.closing_time is None:
        return None
    t = a.closing_time
    return f"{'Order cut-off passed' if t < now else 'Order by'} {_day(t)} {t:%H:%M}"


def reliability_words(p: Product) -> str:
    if p.reliability is None:
        return "no record"
    if p.reliability >= 1.0:
        return "every time"
    return f"{round(p.reliability * 100)} of 100 times"


def reliability_text(p: Product) -> str:
    if p.reliability is None:
        return "No record yet: treated as least reliable"
    return f"Delivered in full {reliability_words(p)}"


def diet_text(p: Product, claims) -> str | None:
    """"Lactose free: Valio confirms", one part per diet the request needs."""
    parts = []
    for c in sorted(claims):
        level, _ = claim_check(p, c)
        name = CLAIM_NAMES.get(c, c)
        parts.append(f"{name[:1].upper()}{name[1:]}: {GRADE_WORDS.get(str(level), str(level))}")
    return ". ".join(parts) or None


def _labels(p: Product, prefer) -> int:
    return len(p.labels & set(prefer or ()))


def decided_by(chosen: Ranked, runner: Ranked | None, cheapest: int, prefer=(), band: float = TIE_BAND) -> str:
    """The Best Pick key that put `chosen` ahead of `runner`, the next accepted option."""
    if runner is None:
        return "only option"
    c, r = chosen.product, runner.product
    if runner.total_cents > cheapest * (1 + band) or chosen.total_cents > cheapest * (1 + band):
        return "price"
    if (c.reliability is None, c.reliability) != (r.reliability is None, r.reliability):
        return "delivery record"
    if _labels(c, prefer) != _labels(r, prefer):
        return "labels"
    if c.carbon_kg_per_kg != r.carbon_kg_per_kg:
        return "footprint"
    return "price"


def why_text(chosen: Ranked, runner: Ranked | None, decided: str, cheapest: int, unit: dict[int, str | None],
             band: float = TIE_BAND) -> str:
    """Two short sentences on why the chosen option won."""
    c = chosen.product
    rel = (f"Valio delivered it in full {reliability_words(c)}." if c.reliability is not None
           else "Valio has no delivery record for it yet.")
    if runner is None:
        return f"The only option that fits and arrives in time. {rel}"
    diff = runner.total_cents - chosen.total_cents
    if decided == "price":
        per = unit.get(id(chosen))
        head = f"Cheapest that fits, at {per}." if per else "Cheapest that fits."
        return f"{head} The next costs {money(diff)} more." if diff > 0 else f"{head} {rel}"
    if chosen.total_cents > cheapest:
        head = (f"Costs {money(chosen.total_cents - cheapest)} more than the cheapest, which your rules count as "
                "the same price.")
    else:
        head = f"Cheapest, and others within {band * 100:g} % count as the same price."
    r = runner.product
    if decided == "delivery record":
        return f"{head} It wins because Valio delivered it in full {reliability_words(c)}, against " \
               f"{reliability_words(r)}."
    if decided == "labels":
        return f"{head} It wins because it has more of the labels you prefer."
    return f"{head} It wins on a lower footprint."


def why_not_text(o: Ranked, chosen: Ranked, cheapest: int, unit: dict[int, str | None], prefer=(),
                 band: float = TIE_BAND) -> str:
    """One sentence on why an accepted option was not the one: "Costs 16.50 € more: 7.86 € per kg against
    7.20 €."."""
    diff = o.total_cents - chosen.total_cents
    if o.total_cents > cheapest * (1 + band):
        mine, theirs = unit.get(id(o)), unit.get(id(chosen))
        if mine and theirs:
            return f"Costs {money(diff)} more: {mine} against {theirs.split(' per ')[0]}."
        return f"Costs {money(diff)} more."
    head = "Same price band" if diff >= 0 else f"Costs {money(-diff)} less, which counts as the same price"
    p, c = o.product, chosen.product
    if (p.reliability is None, p.reliability) != (c.reliability is None, c.reliability):
        return f"{head}, but delivered in full {reliability_words(p)}, against {reliability_words(c)}."
    if _labels(p, prefer) != _labels(c, prefer):
        return f"{head}, but fewer of the labels you prefer."
    if p.carbon_kg_per_kg != c.carbon_kg_per_kg:
        return f"{head}, but a higher footprint."
    return f"{head}, sorted after it."
