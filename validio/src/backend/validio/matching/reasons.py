"""One sentence per Best Pick key, in words a chef understands."""

from ..catalog.labels import LABELS
from ..catalog.model import Product
from ..text.format import and_list, money, sentences


def eur(cents: int) -> str:
    return money(cents)


def price_sentence(total: int, cheapest: int, band: float) -> str:
    if total == cheapest:
        return "Cheapest safe option"
    diff = eur(total - cheapest)
    if total <= cheapest * (1 + band):
        return f"{diff} more than the cheapest, within {band * 100:g} %, so it counts as equal on price"
    return f"{diff} more than the cheapest"


def reliability_sentence(p: Product) -> str:
    if p.reliability is None:
        return "No delivery record in Valio's data, so it sorts last"
    if p.reliability >= 1.0:
        return "Valio delivered it as ordered every time in its records"
    return f"Valio delivered it as ordered {round(p.reliability * 100)} of 100 times"


def label_sentences(p: Product, prefer: tuple[str, ...]) -> list[str]:
    """One sentence for the labels the Spend Pass asks for, one for the others."""
    out = []
    for asked, asks in ((True, "asks for"), (False, "does not ask for")):
        names = [LABELS[c].name if c in LABELS else c for c in sorted(p.labels) if (c in prefer) == asked]
        if names:
            out.append(f"Has the {and_list(names)} label{'s' if len(names) > 1 else ''}, "
                       f"which your Spend Pass {asks}")
    return out


def carbon_sentence(p: Product) -> str:
    if p.carbon_kg_per_kg is None:
        return "No footprint value in Valio's data"
    return f"Footprint {p.carbon_kg_per_kg:g} kg CO2e per kg, a group average"


def option_sentence(why: list[str], reasons: list[str], notes: list[str], accepted: bool,
                    carbon: str | None = None) -> str:
    """The reasons of one option as sentences a chef reads. Accepted: the price and the delivery record in
    one sentence, then labels and the footprint (left out when `carbon` is the footprint the line's note
    already gives for every option). Rejected: each reason once, as its own sentence."""
    if not (accepted and why):
        return sentences(list(reasons) + list(notes)) or "Not usable."
    price, *rest = [w for w in why if w and w != carbon]
    if rest and rest[0].startswith(("Valio delivered", "No delivery record")) and "," not in price:
        rel = rest[0] if rest[0].startswith("Valio") else rest[0][0].lower() + rest[0][1:]
        price, rest = f"{price} and {rel}", rest[1:]
    return sentences([price, *rest])
