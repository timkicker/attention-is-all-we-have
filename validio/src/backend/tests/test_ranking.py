"""Step 13, Best Pick: hard rules, price with a 5 % tie band, delivery record, asked-for labels, carbon.

Each key writes one sentence a chef understands."""

from dataclasses import replace
from datetime import date, datetime

import pytest

from validio.config import load_settings
from validio.matching.need import Ranked, candidates, parse_need
from validio.matching.rank import best_pick, rank
from validio.valio.budget import CallBudget
from validio.valio.client import ValioClient

TODAY = date(2026, 11, 14)
MON = date(2026, 11, 16)
NOW = datetime.fromisoformat("2026-11-14T10:00:00+02:00")
DEMO = "1000 litres of lactose-free milk by Monday, budget 1200 euro"


@pytest.fixture(scope="module")
def valio():
    s = load_settings()
    if not any(s.valio_cache.glob("price/*/*.json")):
        pytest.skip("needs_data: no recorded Valio answers, run make record")
    return ValioClient(s.valio_base_url, "", "replay", s.valio_cache)


@pytest.fixture(scope="module")
def live(catalog, valio):
    need = parse_need(DEMO, TODAY)
    cands = candidates(need, catalog)
    ids = [p.id for p in cands]
    b = CallBudget(40)
    return need, cands, valio.price(ids, MON, b), valio.availability(ids, MON, b)


def scene2(live, **kw):
    need, cands, q, a = live
    return rank(need, cands, q, a, NOW, **kw)


def option(catalog, pid, total, reliability="keep", accepted=True):
    p = catalog.get(pid)
    if reliability != "keep":
        p = replace(p, reliability=reliability)
    return Ranked(p, 1000, total, accepted)


def test_scene2_order_464306_then_464401(live):
    out = scene2(live)
    assert [r.product.id for r in out if r.accepted][:2] == ["464306", "464401"]
    first, second = out[0], out[1]
    assert first.why[0] == "Cheapest safe option"
    assert "Valio delivered it as ordered every time in its records" in first.why
    assert second.why[0] == "90.00 EUR more than the cheapest"
    assert "Has the Heart Symbol label, which your Spend Pass does not ask for" in second.why


def test_tie_band_uses_reliability(catalog):
    # two options 3 % apart: the dearer one was always delivered, the cheaper one 90 of 100 times
    cheap = option(catalog, "464306", 100000, reliability=0.9)
    steady = option(catalog, "464401", 103000, reliability=1.0)
    out = best_pick([cheap, steady])
    assert [r.product.id for r in out] == ["464401", "464306"]
    assert out[0].why[0] == "30.00 EUR more than the cheapest, within 5 %, so it counts as equal on price"
    assert "Valio delivered it as ordered 90 of 100 times" in out[1].why


def test_outside_band_price_wins(catalog):
    cheap = option(catalog, "464306", 100000, reliability=0.9)
    steady = option(catalog, "464401", 106000, reliability=1.0)
    assert [r.product.id for r in best_pick([steady, cheap])] == ["464306", "464401"]


def test_missing_reliability_sorts_last(catalog):
    none = option(catalog, "464306", 99000, reliability=None)
    a = option(catalog, "464401", 100000, reliability=0.95)
    b = option(catalog, "463383", 101000, reliability=0.9)
    out = best_pick([none, a, b])
    assert [r.product.id for r in out] == ["464401", "463383", "464306"]
    assert "No delivery record in Valio's data, so it sorts last" in out[-1].why


def test_prefer_labels_changes_rank(live):
    out = scene2(live, prefer_labels=("FINNISH_HEART_SYMBOL",), band=0.10)
    assert out[0].product.id == "464401" and out[0].total_cents == 110000
    assert "Has the Heart Symbol label, which your Spend Pass asks for" in out[0].why


def test_carbon_sentence_says_group_average(live):
    out = scene2(live)
    assert "Footprint 1.1 kg CO2e per kg, a group average" in out[0].why


def test_rejected_after_accepted_and_every_option_has_sentence(live):
    out = scene2(live)
    flags = [r.accepted for r in out]
    assert flags == sorted(flags, reverse=True)
    for r in out:
        assert r.why, r.product.id
    rejected = {r.product.id: r for r in out if not r.accepted}
    assert rejected["462921"].why == rejected["462921"].reasons


def test_unit_mismatch_counts_sales_units(catalog, valio):
    # 469054: Valio has 36 ST, which is 3 boxes of 12. 10 boxes must not pass the stock check.
    from validio.matching.need import Need
    from validio.matching.rank import rank_one

    p = catalog.get("469054")
    b = CallBudget(40)
    q, a = valio.price([p.id], MON, b)[p.id], valio.availability([p.id], MON, b)[p.id]
    r = rank_one(Need("item", 10, "PCS", set(), set(), MON, None, product_id=p.id), p, q, a, NOW)
    assert r.sales_qty == 10
    assert not r.accepted
    assert any("Only 3 KI in stock" in x for x in r.reasons)
    ok = rank_one(Need("item", 3, "PCS", set(), set(), MON, None, product_id=p.id), p, q, a, NOW)
    assert not any("in stock" in x for x in ok.reasons)
