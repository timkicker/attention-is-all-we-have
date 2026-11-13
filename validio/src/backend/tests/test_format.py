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
    (1000, "ST", "1,000 packs"), (1, "ST", "1 pack"), (200, "BAG", "200 bags"), (1, "BAG", "1 bag"),
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
