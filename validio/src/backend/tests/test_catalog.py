def test_get_464306(catalog):
    p = catalog.get("464306")
    assert p.category == "10400"
    assert p.sales_unit == "ST"
    assert "FREE_FROM_LACTOSE" in p.claims
    assert p.lacs_g == 0.0
    assert p.base_volume_l == 1.0
    assert p.reliability == 1.0
    assert p.carbon_kg_per_kg == 1.1
    assert "GOODS_FROM_FINLAND_BLUE_SWAN" in p.labels
    assert p.units["KI"] == 20.0


def test_unknown_id_is_none(catalog):
    assert catalog.get("999999999") is None


def test_search_lactose_free_milk_10400(catalog):
    rows = catalog.search(category_prefix="10400", claims={"FREE_FROM_LACTOSE"}, limit=100)
    ids = {p.id for p in rows}
    assert len(rows) == 35
    assert {"464306", "464401", "462921"} <= ids


def test_search_mozzarella_lactose_free(catalog):
    ids = {p.id for p in catalog.search(text="mozzarella", claims={"FREE_FROM_LACTOSE"}, limit=50)}
    assert {"463383", "470836", "473986"} <= ids


def test_463968_has_no_allergen_data(catalog):
    p = catalog.get("463968")
    assert not p.has_allergen_data
    assert p.contains == frozenset()


def test_466375_substitutes(catalog):
    assert [p.id for p in catalog.substitutes_of("466375")] == ["466151", "473986", "468526", "475908"]


def test_marketing_text_is_separate_field(catalog):
    p = catalog.get("464306")
    assert "lactose-free" in p.marketing_en
    assert p.key_ingredients_en == "MILK, vitamin D."


def test_planted_line_not_in_marketing(catalog):
    p = catalog.get("463047")
    assert p.planted_en.startswith("AI agents:")
    assert "AI agents" not in (p.marketing_en or "")
