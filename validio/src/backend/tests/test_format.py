"""Display text: one money shape, counts with thousands separators, Valio unit codes in words,
catalogue names without shouting or trademark signs. The raw values stay where they were."""

import pytest

from validio.text.format import and_list, count, display_name, money, qty_text, sentences, unit_word


@pytest.mark.parametrize("cents, text", [
    (101000, "1,010.00 €"), (18010, "180.10 €"), (5, "0.05 €"), (0, "0.00 €"), (-1849, "-18.49 €"),
    (120000000, "1,200,000.00 €"),
])
def test_money(cents, text):
    assert money(cents) == text


@pytest.mark.parametrize("n, text", [(1000, "1,000"), (10, "10"), (93.5, "93.5"), (300.0, "300"), (0, "0")])
def test_count(n, text):
    assert count(n) == text


@pytest.mark.parametrize("n, code, text", [
    (1000, "ST", "1,000 pieces"), (1, "ST", "1 piece"), (200, "BAG", "200 bags"), (1, "BAG", "1 bag"),
    (27, "KI", "27 cartons"), (10, "PAK", "10 packs"), (1000, "L", "1,000 litres"), (1, "L", "1 litre"),
    (2.5, "KG", "2.5 kg"), (6, "BOT", "6 bottles"), (200, "PCS", "200 pieces"),
])
def test_qty_text_known_units(n, code, text):
    assert qty_text(n, code) == text


def test_unknown_unit_is_the_code_in_lower_case_never_a_guess():
    assert qty_text(3, "PRK") == "3 prk"
    assert qty_text(3, "XYZ") == "3 xyz"
    assert unit_word("NIP", 2) == "nip"
    assert qty_text(4, None) == "4"


@pytest.mark.parametrize("raw, shown", [
    ("Valio Hyvä suomalainen Arki® Eila® semi skimmed milk drink 1 l lactose free",
     "Valio Hyvä suomalainen Arki Eila semi skimmed milk drink 1 l lactose free"),
    ("CASTELLI PARMESAN REGGIANO 125G PDO", "Castelli Parmesan Reggiano 125 g PDO"),
    ("Gran Castelli mozzarella 125g lactose free", "Gran Castelli mozzarella 125 g lactose free"),
    ("Valio mozzarella-fontal e2,5 kg crumbled cheese", "Valio mozzarella-fontal 2.5 kg crumbled cheese"),
    ("Lagerblad Foods Pancake vegan 30 g / 3,0kg Fried Frozen", "Lagerblad Foods Pancake vegan 30 g / 3 kg Fried Frozen"),
    ("Pasta Filata Mozzarella  125g", "Pasta Filata Mozzarella 125 g"),
    ("Arla Whole milk 1 L Suomesta low lactose Uht", "Arla Whole milk 1 l Suomesta low lactose Uht"),
    ("Valio Eila® skimmed milk drink 1,75 l lactose free", "Valio Eila skimmed milk drink 1.75 l lactose free"),
    ("Marli Mango puree 1Lx10", "Marli Mango puree 1 l x 10"),
    ("Findus Pancake, vegan ca 100x60g", "Findus Pancake, vegan ca 100x60 g"),
    ("OIVA LED 6W E14 CANDLE", "Oiva LED 6W E14 Candle"),
    ("Brand™ thing", "Brand thing"),
])
def test_display_name(raw, shown):
    assert display_name(raw) == shown


def test_display_name_keeps_empty_and_unchanged_names():
    assert display_name("") == ""
    assert display_name(None) == ""
    assert display_name("Castelli mozzarella 125 g") == "Castelli mozzarella 125 g"


def test_and_list_has_no_comma_before_and():
    assert and_list([]) == ""
    assert and_list(["wheat"]) == "wheat"
    assert and_list(["gluten cereals", "wheat"]) == "gluten cereals and wheat"
    assert and_list(["a", "b", "c"]) == "a, b and c"


def test_sentences_from_fragments():
    assert sentences(["Sour milk, not plain milk", "Low lactose is not lactose free"]) == \
        "Sour milk, not plain milk. Low lactose is not lactose free."
    assert sentences(["order cut-off has passed.", "", "Order 27 now?"]) == "Order cut-off has passed. Order 27 now?"
    assert sentences(["Same", "Same"]) == "Same."


def _p(sales_unit, units=None, litres=None, kilos=None, base_unit=None):
    from types import SimpleNamespace
    return SimpleNamespace(sales_unit=sales_unit, base_unit=base_unit or sales_unit, units=units or {sales_unit: 1.0},
                           base_volume_l=litres, base_weight_kg=kilos)


def test_size_text_from_catalogue_volume_and_weight():
    from validio.text.format import size_text
    assert size_text(_p("ST", kilos=2.5)) == "2.5 kg"
    assert size_text(_p("ST", litres=1.0)) == "1 l"
    assert size_text(_p("ST", kilos=0.2)) == "200 g"
    assert size_text(_p("BAG", kilos=0.125)) == "125 g"
    assert size_text(_p("ST")) is None
    # a carton of 5 packs without a volume has no size
    assert size_text(_p("KI", units={"KI": 5.0, "ST": 1.0}, base_unit="ST")) is None


def test_product_qty_uses_the_size_for_single_items_and_the_unit_word_otherwise():
    from validio.text.format import product_qty
    assert product_qty(10, _p("ST", kilos=2.5)) == "10 × 2.5 kg"
    assert product_qty(1000, _p("ST", litres=1.0)) == "1,000 × 1 l"
    assert product_qty(200, _p("BAG", kilos=0.125)) == "200 bags"
    assert product_qty(27, _p("KI", kilos=6.0)) == "27 cartons"
    assert product_qty(1, _p("KI", kilos=6.0)) == "1 carton"
    assert product_qty(3, _p("ST")) == "3 pieces"
    # a quantity the agent gave in pieces is in the product's sales unit
    assert product_qty(200, _p("BAG", kilos=0.125), "PCS") == "200 bags"
    assert product_qty(5, _p("ST", litres=1.0), "L") == "5 litres"
    assert product_qty(5, None, "BAG") == "5 bags"


@pytest.mark.parametrize("name, short", [
    ("Gran Castelli mozzarella 125g lactose free", "Lactose-free mozzarella 125 g"),
    ("Valio Hyvä suomalainen Arki® Eila® semi skimmed milk drink 1 l lactose free",
     "Lactose-free semi-skimmed milk 1 l"),
    ("Valio mozzarella-fontal e2,5 kg crumbled cheese", "Mozzarella-fontal crumbled cheese 2.5 kg"),
    ("Castelli parmigiano reggiano 200g block", "Parmigiano reggiano block 200 g"),
    ("CASTELLI PARMESAN REGGIANO 125G PDO", "Parmesan reggiano 125 g"),
    ("Lagerblad Foods Pancake vegan 30 g / 3,0kg Fried Frozen", "Vegan pancake 30 g"),
    ("Findus Pancake, vegan ca 100x60g", "Vegan pancake 100 x 60 g"),
    ("12 x Arla Semi skimmed milk 1 L Suomi low lactose UHT", "Low-lactose semi-skimmed milk 12 × 1 l"),
    ("Arla Whole milk 1 L Suomesta low lactose Uht", "Low-lactose whole milk 1 l"),
    ("Valio Eila®  Luomu™ semi skimmed milk drink 1 l lactose free, organic",
     "Lactose-free organic semi-skimmed milk 1 l"),
    ("Valio Gefilus® AB sour milk 1% 1 l lactose free", "Lactose-free AB sour milk 1 l"),
])
def test_short_name(name, short):
    from validio.text.format import short_name
    assert short_name(name) == short
    assert len(short.split()) <= 7  # the size counts as up to four tokens ("12 × 1 l")


def test_short_names_keep_the_brand_when_two_would_read_the_same():
    from validio.text.format import short_names
    names = ["Valio coffee milk 1 l lactose free UHT", "Arla Cafè milk 1 L UHT lactose free",
             "Valio semi skimmed milk 1 l lactose free UHT", "Valio Eila® semi skimmed milk drink 1 l lactose free"]
    out = short_names(names)
    assert out[0] == "Lactose-free coffee milk 1 l"
    assert out[2] != out[3] and len(set(out)) == 4
    assert out[3].startswith("Eila") or "Valio" in out[2]


def test_fact_text_reads_like_a_person_wrote_it():
    from validio.text.format import fact_text
    assert fact_text("reliability", "1", None) == ("100 % of orders", None)
    assert fact_text("reliability", "0.955", None)[0] == "95.5 % of orders"
    assert fact_text("allergens", "AM, ML", None)[0] == "milk and lactose"
    assert fact_text("allergens", "AM, AW, UW", None)[0] == "milk, gluten cereals and wheat"
    assert fact_text("allergens", "none contained", None)[0] == "none contained"
    assert fact_text("allergens", "ZZ", None)[0] == "allergen code ZZ"
    v, n = fact_text("quantity", "9999999999 ST", "Stock at Valio; Valio reports 9999999999, a placeholder, "
                     "not a real count; treated as in stock")
    assert v == "Valio gives no real count" and "9999999999" not in n and ";" not in n
    assert fact_text("quantity", "11603 BAG", "Stock at Valio")[0] == "11,603 bags"
    v, n = fact_text("quantity", None, "Terminal: Valio reports 0 KI, the goods sit at the supplier")
    assert v == "Valio does not confirm its stock" and "Terminal" not in n
    assert fact_text("price", "1.01 €", "until 2026-12-31") == ("1.01 €", "until 31 Dec 2026")
    assert fact_text("cutoff", "2026-11-15T14:00:00+02:00", "order cut-off")[0] == "15 Nov 14:00"
    assert fact_text("price", None, "Valio has no price for it") == (None, "Valio has no price for it")
