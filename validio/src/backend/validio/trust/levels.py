"""Fact Grades: every fact Validio uses carries how far it can be trusted. Unknown is never safe."""

from dataclasses import dataclass
from enum import StrEnum

from ..catalog.labels import LABELS
from ..catalog.model import Product
from ..valio.models import Availability, Quote


class TrustLevel(StrEnum):
    ATTESTED = "attested"  # Valio says it directly
    ATTESTED_UNTIL = "attested_until"  # a price with an end date
    CONSISTENT = "consistent"  # a claim the other fields back up
    CONTRADICTED = "contradicted"  # a claim another field disproves
    UNCHECKED = "unchecked"  # a claim nothing can confirm
    UNKNOWN = "unknown"  # Valio does not know it either
    UNTRUSTED = "untrusted"  # supplier text, shown, never used for a decision
    MISSING = "missing"  # the field is not there


@dataclass(frozen=True)
class Fact:
    field: str
    value: str | None
    level: TrustLevel
    source: str
    note: str = ""


UNKNOWN_AMOUNT = 999999
AVAIL = "Valio availability API"
PRICE = "Valio price API"
MASTER = "Valio product data"


def unit_factor(p: Product, unit: str) -> float | None:
    """How many of the product's sales units one `unit` is. None when the catalog does not give both sizes."""
    if unit == p.sales_unit:
        return 1.0

    def size(u: str) -> float | None:
        return p.units.get(u) or (1.0 if u == p.base_unit else None)

    have, sell = size(unit), size(p.sales_unit)
    return have / sell if have and sell else None


def quantity_fact(a: Availability | None, p: Product | None = None) -> Fact:
    """Valio's amount is in the unit of its schedule line. With the product, a unit that cannot be converted
    to the product's sales unit makes the quantity unknown."""
    if a is None:
        return Fact("quantity", None, TrustLevel.MISSING, AVAIL, "not asked")
    if not a.lines:
        return Fact("quantity", "not deliverable", TrustLevel.ATTESTED, AVAIL, "Valio gives no delivery line")
    unit = a.lines[0].sales_unit
    if a.logistic_model == "Terminal" or a.amount == UNKNOWN_AMOUNT:
        return Fact("quantity", None, TrustLevel.UNKNOWN, AVAIL,
                    f"{a.logistic_model}: Valio reports {a.amount:g} {unit}, the goods sit at the supplier")
    note = f"{a.logistic_model} at Valio"
    if p is not None and unit != p.sales_unit:
        factor = unit_factor(p, unit)
        if factor is None:
            return Fact("quantity", f"{a.amount:g} {unit}", TrustLevel.UNKNOWN, AVAIL,
                        f"Valio counts in {unit}, the product is sold in {p.sales_unit}, no conversion known")
        note += f", {a.amount * factor:g} {p.sales_unit} in sales units"
    return Fact("quantity", f"{a.amount:g} {unit}", TrustLevel.ATTESTED, AVAIL, note)


def stock_in_sales_units(p: Product, a: Availability | None) -> float | None:
    """Stock Valio attests, in the product's sales unit. None when it is not deliverable or not a real count."""
    if a is None or not a.deliverable or quantity_fact(a, p).level != TrustLevel.ATTESTED:
        return None
    return a.amount * unit_factor(p, a.lines[0].sales_unit)


def price_fact(q: Quote | None) -> Fact:
    if q is None or q.error or q.price_cents is None:
        return Fact("price", None, TrustLevel.MISSING, PRICE, "Valio has no price for it")
    value = f"{q.price_cents / 100:.2f} EUR"
    if q.valid_to:
        return Fact("price", value, TrustLevel.ATTESTED_UNTIL, PRICE, f"until {q.valid_to.isoformat()}")
    return Fact("price", value, TrustLevel.ATTESTED, PRICE, "catalog price, no end date")


def field_trust(p: Product, q: Quote | None, a: Availability | None) -> list[Fact]:
    from .claims import claim_check

    out = [quantity_fact(a, p), price_fact(q)]
    if a is not None and a.closing_time:
        out.append(Fact("cutoff", a.closing_time.isoformat(), TrustLevel.ATTESTED, AVAIL, "order cut-off"))
    if p.reliability is None:
        out.append(Fact("reliability", None, TrustLevel.MISSING, "Valio delivery reliability file",
                        "no delivery record"))
    else:
        out.append(Fact("reliability", f"{p.reliability:g}", TrustLevel.ATTESTED, "Valio delivery reliability file",
                        "share delivered as ordered"))
    if p.carbon_kg_per_kg is None:
        out.append(Fact("carbon", None, TrustLevel.MISSING, "Valio carbon footprint file", "no value"))
    else:
        out.append(Fact("carbon", f"{p.carbon_kg_per_kg:g} kg CO2e per kg", TrustLevel.ATTESTED,
                        "Valio carbon footprint file", "group average for its product group"))
    for code in sorted(p.labels):
        name = LABELS[code].name if code in LABELS else code
        out.append(Fact(f"label:{code}", name, TrustLevel.ATTESTED, MASTER))
    if p.has_allergen_data:
        out.append(Fact("allergens", ", ".join(sorted(p.contains)) or "none contained", TrustLevel.ATTESTED, MASTER,
                        "may contain: " + (", ".join(sorted(p.may_contain)) or "none")))
    else:
        out.append(Fact("allergens", None, TrustLevel.MISSING, MASTER, "no allergen data at all"))
    for claim in sorted(p.claims):
        level, notes = claim_check(p, claim)
        out.append(Fact(f"claim:{claim}", claim, level, MASTER, "; ".join(notes)))
    out.append(Fact("description", p.marketing_en, TrustLevel.UNTRUSTED, "supplier text", "never used for a decision"))
    out.append(Fact("key_ingredients", p.key_ingredients_en, TrustLevel.UNTRUSTED, "supplier text",
                    "read only to find contradictions"))
    if p.planted_en:
        out.append(Fact("planted_line", p.planted_en, TrustLevel.UNTRUSTED, "demo",
                        "planted by the team for this demo"))
    return out
