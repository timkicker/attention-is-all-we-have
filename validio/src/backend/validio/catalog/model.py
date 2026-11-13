from dataclasses import dataclass


@dataclass(frozen=True)
class Product:
    id: str
    name_en: str
    name_fi: str | None
    category: str
    vendor: str
    sales_unit: str
    base_unit: str
    units: dict[str, float]  # unit id -> size in base units
    base_volume_l: float | None  # litres per base unit, None when Valio gives no volume
    base_weight_kg: float | None  # kilos per base unit
    claims: frozenset[str]
    contains: frozenset[str]
    may_contain: frozenset[str]
    free_from: frozenset[str]
    has_allergen_data: bool
    lacs_g: float | None  # lactose g per 100 g from nutritionFact, None when missing
    key_ingredients_en: str | None  # supplier text, used only to find contradictions
    marketing_en: str | None  # supplier text, untrusted, display only
    planted_en: str | None  # our planted demo line, kept apart from Valio's text
    substitutes: tuple[str, ...]  # Valio's order
    reliability: float | None
    carbon_kg_per_kg: float | None  # product group average
    labels: frozenset[str]
    temperature: int | None
    deleted: bool
