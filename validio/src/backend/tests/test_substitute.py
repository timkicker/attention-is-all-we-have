"""Step 9, Safe Swap: Valio's list first, in Valio's order, then at most 8 extra ids from the catalog.

Scene 3: 200 bags of 466375 (25 kg lactose-free mozzarella) after the simulated stock-out."""

from datetime import date, datetime

import pytest

from validio.config import load_settings
from validio.matching.need import Need
from validio.matching.substitute import MAX_EXTRA_IDS, SubVerdict, safe_swap
from validio.valio.budget import CallBudget
from validio.valio.client import ValioClient

MON = date(2026, 11, 16)
NOW = datetime.fromisoformat("2026-11-14T10:00:00+02:00")


@pytest.fixture(scope="module")
def valio():
    s = load_settings()
    if not any(s.valio_cache.glob("price/*/*.json")):
        pytest.skip("needs_data: no recorded Valio answers, run make record")
    return ValioClient(s.valio_base_url, "", "replay", s.valio_cache)


def mozzarella_need(pid="466375"):
    return Need(kind="mozzarella", quantity=25, unit="KG", required_claims={"FREE_FROM_LACTOSE"},
                excluded_claims=set(), deliver_by=MON, budget_cents=None, product_id=pid)


@pytest.fixture(scope="module")
def scene3(catalog, valio):
    b = CallBudget(40)
    return safe_swap(catalog.get("466375"), mozzarella_need(), catalog, valio, MON, b, NOW), b


def test_466375_three_listed_blocked(scene3):
    r, _ = scene3
    assert [o.product.id for o in r.listed] == ["466151", "473986", "468526", "475908"]  # Valio's order
    v = {o.product.id: o for o in r.listed}
    for pid in ("466151", "468526", "475908"):
        assert v[pid].verdict is SubVerdict.BLOCKED_DIET
        assert v[pid].sentence == "Lists milk and has no lactose-free claim in Valio's data"


def test_473986_undeliverable(scene3):
    o = {o.product.id: o for o in scene3[0].listed}["473986"]
    assert o.verdict is SubVerdict.UNDELIVERABLE
    assert o.sentence == "Lactose free and checked, but Valio gives no delivery date for it"


def test_outside_search_ranks_cheapest_safe_first(scene3):
    r, _ = scene3
    assert r.searched_outside
    ok = [o for o in r.outside if o.verdict is SubVerdict.OUTSIDE_LIST]
    # The plan expected 463383 to win. The recorded data has a cheaper safe one:
    # 465256 Valio mozzarella-fontal 2.5 kg, lactose 0 g, 10 bags for 180.10 EUR.
    assert [o.product.id for o in ok][:2] == ["465256", "463383"]
    assert r.best.product.id == "465256"
    assert (r.best.ranked.sales_qty, r.best.ranked.total_cents) == (10, 18010)
    ids = [o.product.id for o in ok]
    assert ids.index("463383") < ids.index("470836")


def test_463383_ten_bags_19660(scene3):
    o = {o.product.id: o for o in scene3[0].outside}["463383"]
    assert (o.ranked.sales_qty, o.product.sales_unit, o.ranked.total_cents) == (10, "BAG", 19660)
    assert o.verdict is SubVerdict.OUTSIDE_LIST and not o.on_valio_list


def test_470836_63_units_33453(scene3):
    o = {o.product.id: o for o in scene3[0].outside}["470836"]
    assert (o.ranked.sales_qty, o.ranked.total_cents) == (63, 33453)
    assert any("unchecked" in n for n in o.ranked.notes)


def test_outside_list_goes_to_a_person(scene3):
    r, _ = scene3
    assert r.needs_person
    assert "not on Valio's list" in r.sentence


def test_outside_search_at_most_8_extra_ids(scene3):
    r, b = scene3
    assert len(r.extra_ids) <= MAX_EXTRA_IDS
    assert "466375" not in r.extra_ids and not set(r.extra_ids) & {"466151", "473986", "468526", "475908"}
    # only 473986 of the listed ones keeps the diet, so only it is asked live
    assert b.ids == {"473986", *r.extra_ids}
    assert b.ids_sent <= 40


def test_diet_blocked_substitutes_cost_no_live_call(scene3):
    _, b = scene3
    assert not b.ids & {"466151", "468526", "475908"}


def test_468465_substitute_470863_blocked_gluten(catalog, valio):
    n = Need(kind="oat_drink", quantity=100, unit="L", required_claims={"FREE_FROM_GLUTEN"},
             excluded_claims=set(), deliver_by=MON, budget_cents=None, product_id="468465")
    r = safe_swap(catalog.get("468465"), n, catalog, valio, MON, CallBudget(40), NOW, search_outside=False)
    o = r.listed[0]
    assert o.product.id == "470863" and o.verdict is SubVerdict.BLOCKED_DIET
    assert "gluten" in o.sentence


def test_no_outside_search_when_listed_ok(catalog, valio):
    # 463968 parmesan, no diet on the line: its first listed substitute 469648 can be delivered
    n = Need(kind="parmesan", quantity=200, unit="PCS", required_claims=set(), excluded_claims=set(),
             deliver_by=MON, budget_cents=None, product_id="463968")
    b = CallBudget(40)
    r = safe_swap(catalog.get("463968"), n, catalog, valio, MON, b, NOW)
    assert not r.searched_outside and r.outside == []
    assert r.best.product.id == "469648" and r.best.verdict is SubVerdict.OK_LISTED
    assert {o.product.id: o.verdict for o in r.listed}["471863"] is SubVerdict.UNDELIVERABLE
    assert b.ids == {"469648", "471863"}
