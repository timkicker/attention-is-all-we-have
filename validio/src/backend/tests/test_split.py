"""Step 14, Split Fill: the ordered product up to its attested stock, then Valio's listed substitutes.

Scene 4: parmesan 463968 (200 packs wanted, 137 in stock) and vegan gluten-free pancakes 471376
(30 cartons wanted, 27 in stock)."""

from dataclasses import replace
from datetime import date, datetime

import pytest

from validio.config import load_settings
from validio.matching.split import decide_split, split_fill
from validio.policy.decide import Outcome
from validio.policy.mandate import Mandate
from validio.valio.budget import CallBudget
from validio.valio.client import ValioClient

MON = date(2026, 11, 16)
NOW = datetime.fromisoformat("2026-11-14T10:00:00+02:00")
GLUTEN_FREE_VEGAN = {"FREE_FROM_GLUTEN", "VEGAN"}

DEMO_MANDATE = Mandate(
    id="M-1", issuer="kitchen:hotel-espoo", holder="agent:buyer-1", not_before=1794643200,
    expires=1794866400, categories=("104", "106", "418"), deliver_by="2026-11-16",
    substitutes="listed_and_rules_kept", split_max_extra_bp=500, split_allow_listed=True,
    auto_limit_cents=120000, hard_cap_cents=200000, diet=("FREE_FROM_LACTOSE",), prefer_labels=(),
    disclosed={},
)


@pytest.fixture(scope="module")
def valio():
    s = load_settings()
    if not any(s.valio_cache.glob("price/*/*.json")):
        pytest.skip("needs_data: no recorded Valio answers, run make record")
    return ValioClient(s.valio_base_url, "", "replay", s.valio_cache)


def fill(catalog, valio, pid, wanted, claims=frozenset(), max_extra_bp=500):
    return split_fill(catalog.get(pid), wanted, set(claims), catalog, valio, MON, CallBudget(40),
                      max_extra_bp=max_extra_bp)


@pytest.fixture(scope="module")
def parmesan(catalog, valio):
    return fill(catalog, valio, "463968", 200)


@pytest.fixture(scope="module")
def pancakes(catalog, valio):
    return fill(catalog, valio, "471376", 30, GLUTEN_FREE_VEGAN)


def test_parmesan_split_137_plus_40(parmesan):
    p = parmesan
    assert [(x.product.id, x.sales_qty) for x in p.parts] == [("463968", 137), ("469648", 40)]
    assert (p.base_cents, p.total_cents) == (75400, 77249)
    assert p.extra_pct == "2.5"
    assert p.breaks == [] and p.complete and not p.needs_person
    assert p.parts[1].on_valio_list
    assert p.sentence == ("137 packs of Castelli Parmesan Reggiano 125 g PDO plus 40 packs of Castelli parmigiano "
                          "reggiano 200 g block from Valio's own substitute list for 772.49 €. "
                          "18.49 € (2.5 %) more, inside your 5 % split limit")


def test_pancake_split_breaks_gluten(pancakes):
    p = pancakes
    assert [(x.product.id, x.sales_qty) for x in p.parts] == [("471376", 27)]
    assert [r.id for r, _ in p.refused] == ["476523"]
    assert len(p.breaks) == 1 and "wheat" in p.breaks[0] and "Findus Pancake" in p.breaks[0]
    assert p.covered == pytest.approx(0.9)
    assert not p.complete and p.needs_person
    assert p.sentence.startswith("27 of 30 cartons can come.")


def test_split_skips_undeliverable(catalog, valio):
    # 1000 packs: 137 of 463968 and all 318 of 469648 still fall short, then 471863 has no delivery line
    p = fill(catalog, valio, "463968", 1000)
    assert [(x.product.id, x.sales_qty) for x in p.parts] == [("463968", 137), ("469648", 318)]
    assert [s.id for s, _ in p.skipped] == ["471863"]
    assert p.breaks == [] and not p.complete


def test_split_over_cost_limit_escalates(catalog, valio):
    p = fill(catalog, valio, "463968", 200, max_extra_bp=200)
    assert [x.product.id for x in p.parts] == ["463968"]
    assert p.breaks == [("Castelli parmigiano reggiano 200 g block would break a rule. "
                         "The split would cost 2.5 % more, over your 2 % split limit")]
    assert p.needs_person


def test_no_split_when_stock_enough(catalog, valio):
    assert fill(catalog, valio, "464306", 1000, {"FREE_FROM_LACTOSE"}) is None


def test_split_asks_only_first_and_listed_live(catalog, valio):
    b = CallBudget(40)
    split_fill(catalog.get("463968"), 200, set(), catalog, valio, MON, b)
    assert b.ids == {"463968", "469648", "471863"}


def test_parmesan_split_allowed_by_hard_lines_without_diet(parmesan):
    d = decide_split(parmesan, replace(DEMO_MANDATE, diet=()), NOW)
    assert d.outcome is Outcome.ALLOW and "auto-order" in d.rule_ids
    assert d.context["isSplit"] and d.context["splitExtraBp"] == 246


def test_parmesan_split_renews_alone_under_lactose_free_pass(parmesan):
    # The diet rule applies per line: the parmesan line asks for no diet, so the pass's lactose free does not apply.
    d = decide_split(parmesan, DEMO_MANDATE, NOW, required_claims=())
    assert d.outcome is Outcome.ALLOW and "auto-order" in d.rule_ids
    assert d.context["splitExtraBp"] == 246


def test_split_for_a_lactose_free_line_needs_person(parmesan):
    # Neither parmesan claims lactose free, so a line that needs lactose free still waits for a person.
    for claims in (None, ("FREE_FROM_LACTOSE",)):
        d = decide_split(parmesan, DEMO_MANDATE, NOW, required_claims=claims)
        assert d.outcome is Outcome.ESCALATE
        assert "a diet rule cannot be checked" in d.sentence


def test_incomplete_split_is_not_decided_alone(pancakes):
    with pytest.raises(ValueError):
        decide_split(pancakes, replace(DEMO_MANDATE, diet=()), NOW)


def test_split_stock_in_sales_units(catalog, valio):
    # 469054 is sold in boxes of 12 and Valio answers 36 ST: Split Fill may plan 3 boxes, not 36
    from validio.matching.split import _stock

    a = valio.availability(["469054"], MON, CallBudget(40))["469054"]
    assert _stock(catalog.get("469054"), a) == 3
