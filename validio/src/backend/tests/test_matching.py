from datetime import date, datetime

import pytest

from validio.config import load_settings
from validio.matching.need import (
    Need,
    candidates,
    kg_per_sales_unit,
    litres_per_sales_unit,
    parse_need,
    screen,
)
from validio.matching.rank import rank
from validio.valio.budget import CallBudget
from validio.valio.client import ValioClient

TODAY = date(2026, 11, 14)  # Saturday, the frozen demo clock
NOW = datetime.fromisoformat("2026-11-14T10:00:00+02:00")
MON = date(2026, 11, 16)
DEMO = "1000 litres of lactose-free milk by Monday, budget 1200 euro"


@pytest.fixture(scope="module")
def valio():
    s = load_settings()
    if not any(s.valio_cache.glob("price/*/*.json")):
        pytest.skip("needs_data: no recorded Valio answers, run make record")
    return ValioClient(s.valio_base_url, "", "replay", s.valio_cache)


@pytest.fixture(scope="module")
def milk():
    return parse_need(DEMO, TODAY)


@pytest.fixture(scope="module")
def ranked(milk, catalog, valio):
    cands = candidates(milk, catalog)
    ids = [p.id for p in cands]
    b = CallBudget(40)
    out = rank(milk, cands, valio.price(ids, MON, b), valio.availability(ids, MON, b), NOW)
    return {r.product.id: r for r in out}, out, b


def test_parse_demo_request(milk):
    assert milk.kind == "milk"
    assert (milk.quantity, milk.unit) == (1000, "L")
    assert milk.required_claims == {"FREE_FROM_LACTOSE"}
    assert "LOW_LACTOSE" in milk.excluded_claims
    assert milk.deliver_by == MON
    assert milk.budget_cents == 120000


def test_parse_without_budget():
    n = parse_need("1000 litres of lactose-free milk by Monday", TODAY)
    assert n.budget_cents is None and n.quantity == 1000


def test_litres_464306_one_carton(catalog, valio):
    q = valio.price(["464306"], MON, CallBudget(40))["464306"]
    assert litres_per_sales_unit(catalog.get("464306"), q)[0] == 1.0


def test_1000l_464306_is_1000_ST(ranked):
    r = ranked[0]["464306"]
    assert (r.sales_qty, r.product.sales_unit, r.total_cents) == (1000, "ST", 101000)
    assert r.accepted


def test_1000l_463038_is_50_KI(catalog, valio, ranked):
    p = catalog.get("463038")
    q = valio.price(["463038"], MON, CallBudget(40))["463038"]
    assert litres_per_sales_unit(p, q)[0] == 20.0  # name 10 l times 2, agrees with 3131 / 157 = 19.94 l
    r = ranked[0]["463038"]
    assert (r.sales_qty, r.product.sales_unit, r.total_cents) == (50, "KI", 156550)


def test_462921_200_KI_219400(ranked):
    r = ranked[0]["462921"]
    assert (r.sales_qty, r.product.sales_unit, r.total_cents) == (200, "KI", 219400)


def test_463038_rejected_cutoff_and_unknown_quantity(ranked):
    r = ranked[0]["463038"]
    assert not r.accepted
    assert any("12 Nov 15:00 has passed" in s for s in r.reasons)
    assert any("quantity is unknown" in s for s in r.notes + r.reasons)


def test_462703_rejected_not_milk(milk, catalog):
    _, dropped = screen(milk, catalog)
    r = {d.product.id: d for d in dropped}["462703"]
    assert not r.accepted
    assert r.reasons == ["Lactose free but a cooking fat mix, not milk"]


def test_low_lactose_rejected(milk, catalog):
    _, dropped = screen(milk, catalog)
    d = {x.product.id: x for x in dropped}
    for pid in ("463047", "469541"):
        assert not d[pid].accepted
        assert d[pid].reasons == ["Low lactose is not lactose free"]


def test_off_type_sentence(milk, catalog):
    _, dropped = screen(milk, catalog)
    assert {d.product.id: d for d in dropped}["472492"].reasons == ["Sour milk, not plain milk"]


def test_rejections_have_reasons(milk, catalog, ranked):
    _, dropped = screen(milk, catalog)
    for r in dropped + ranked[1]:
        assert r.accepted or r.reasons, r.product.id


def test_candidates_at_most_12(milk, catalog):
    c = candidates(milk, catalog)
    assert 0 < len(c) <= 12
    assert {"464306", "464401", "463038", "462921"} <= {p.id for p in c}


def test_screen_makes_no_live_call(milk, catalog):
    import respx

    with respx.mock(assert_all_called=False) as mock:
        route = mock.route()
        screen(milk, catalog)
        assert route.call_count == 0


def test_scene2_cheapest_is_464306_and_464401_second(ranked):
    accepted = [r.product.id for r in ranked[1] if r.accepted]
    assert accepted[:2] == ["464306", "464401"]
    assert ranked[0]["464401"].total_cents == 110000


def test_scene2_within_budget(ranked):
    b = ranked[2]
    assert b.ids_sent <= 12 and b.calls == 2


def test_narrowing_hides_no_cheaper_safe_milk(milk, catalog, valio):
    """Every statically fine milk left out by the cap of 12 is dearer per litre than the pick."""
    kept, _ = screen(milk, catalog, limit=None)
    ids = [p.id for p in kept]
    b = CallBudget(len(ids))
    q = valio.price(ids, MON, b)
    for p in kept:
        if p.id in {c.id for c in candidates(milk, catalog)}:
            continue
        litres = litres_per_sales_unit(p, q[p.id])[0]
        assert litres is None or q[p.id].price_cents / litres > 101, p.id


def test_kg_466375_and_463383(catalog, valio):
    q = valio.price(["466375", "463383"], MON, CallBudget(40))
    assert kg_per_sales_unit(catalog.get("466375"), q["466375"])[0] == 0.125
    assert kg_per_sales_unit(catalog.get("463383"), q["463383"])[0] == 2.5


def test_product_need_fixed_id(catalog):
    n = Need(kind="mozzarella", quantity=25, unit="KG", required_claims={"FREE_FROM_LACTOSE"},
             excluded_claims=set(), deliver_by=MON, budget_cents=None, product_id="466375")
    assert [p.id for p in candidates(n, catalog)] == ["466375"]


# play audit: any product word the catalogue knows, not a fixed list


@pytest.mark.parametrize("text,kind,qty,unit,claims", [
    ("20 kg of parmesan by Monday", "parmesan", 20, "KG", set()),
    ("100 litres of lactose-free cream by Monday", "cream", 100, "L", {"FREE_FROM_LACTOSE"}),
    ("30 cartons of vegan pancakes by Monday", "pancake", 30, "PCS", {"VEGAN"}),
])
def test_any_catalogue_word_is_a_kind(catalog, text, kind, qty, unit, claims):
    n = parse_need(text, TODAY, catalog)
    assert (n.kind, n.quantity, n.unit, n.required_claims) == (kind, qty, unit, claims)
    kept, dropped = screen(n, catalog)
    assert kept or dropped  # the catalogue search finds products of that kind


def test_a_word_the_catalogue_does_not_know_is_refused(catalog):
    with pytest.raises(ValueError, match="no known product kind"):
        parse_need("50 kg of unobtainium", TODAY, catalog)


def test_without_a_catalogue_only_the_fixed_kinds():
    with pytest.raises(ValueError, match="no known product kind"):
        parse_need("20 kg of parmesan", TODAY)


def test_two_words_before_one_and_cream_is_dairy(catalog):
    from validio.matching.need import kind_of

    n = parse_need("100 litres of whipping cream by Monday", TODAY, catalog)
    assert n.kind == "whipping cream"
    cream = parse_need("200 litres of cream by Monday", TODAY, catalog)
    assert kind_of(cream.kind).net == ("10401",)  # not ice cream, which most names with "cream" are
    kept, _ = screen(cream, catalog)
    assert kept and all(p.category.startswith("10401") for p in kept)
