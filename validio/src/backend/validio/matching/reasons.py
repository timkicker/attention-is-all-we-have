"""One sentence per Best Pick key, in words a chef understands."""

from ..catalog.labels import LABELS
from ..catalog.model import Product


def eur(cents: int) -> str:
    return f"{cents // 100}.{cents % 100:02d} EUR"


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
    out = []
    for code in sorted(p.labels):
        name = LABELS[code].name if code in LABELS else code
        asks = "asks for" if code in prefer else "does not ask for"
        out.append(f"Has the {name}, which your Spend Pass {asks}")
    return out


def carbon_sentence(p: Product) -> str:
    if p.carbon_kg_per_kg is None:
        return "No footprint value in Valio's data"
    return f"Footprint {p.carbon_kg_per_kg:g} kg CO2e per kg, a group average"
