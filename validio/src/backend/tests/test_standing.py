"""Step 15, Steady Orders and Drift Watch.

Acceptance from the blueprint: the mozzarella flag shows 26 % more per guest (last 2 weeks against the first 4),
parmesan renews alone (split 137 x 463968 plus 40 x 469648, 772.49 EUR, 2.5 % more), pancakes wait for the chef
(471376 covers 27 of 30, 476523 contains wheat). Thresholds: per guest +20 %, cost +10 % over the median,
a contract price that ends before the next 4 renewals, stock below the usual line.

Split Fill (matching/split.py) and the Hard Lines decision on it are the real ones, the diet rule is per line."""

from dataclasses import replace
from datetime import date, timedelta

import pytest

from validio.config import load_settings
from validio.demo import seed
from validio.matching.split import plan_split
from validio.standing.drift import detect, next_renewals
from validio.standing.learn import NotEnoughHistory, learn
from validio.standing.model import DriftKind, History, LineResult, PastOrder
from validio.standing.renew import accept, fetch, renew, run
from validio.valio.client import ValioClient
from validio.valio.models import Quote

NOW = seed.NOW
MON = date(2026, 11, 16)


@pytest.fixture(scope="module")
def valio():
    s = load_settings()
    if not any(s.valio_cache.glob("price/*/*.json")):
        pytest.skip(f"needs_data: no recorded Valio answers in {s.valio_cache}, run make record")
    return ValioClient(s.valio_base_url, "", "replay", s.valio_cache)


@pytest.fixture(scope="module")
def mandate(tmp_path_factory):
    d = tmp_path_factory.mktemp("seed")
    seed.reset(d / "v.db", keys_dir=d / "keys")
    return seed.spend_pass(d / "v.db", keys_dir=d / "keys")


@pytest.fixture(scope="module")
def history():
    return seed.load_history()


@pytest.fixture(scope="module")
def so(history):
    return learn(history)


class Recorder:
    """Real Split Fill, records which lines were sent to it."""

    def __init__(self):
        self.asked: list[str] = []

    def __call__(self, first, *args):
        self.asked.append(first.id)
        return plan_split(first, *args)


@pytest.fixture(scope="module")
def renewal(so, history, catalog, valio, mandate):
    return run(so, history, catalog, valio, mandate, NOW, stockout=False)


def line(r, pid):
    return next(x for x in r.lines if x.product_id == pid)


# --- learning ---


def test_learn_median_from_history(so):
    usual = {ln.product_id: ln.sales_qty for ln in so.lines}
    assert usual == {"464306": 300, "463968": 200, "471376": 30, "466375": 98}  # median of 92..120 is 98
    assert so.guests == 400
    assert so.learned_from == 8
    assert so.weekday == 0


def test_learn_keeps_line_diet(so):
    diet = {ln.product_id: ln.diet for ln in so.lines}
    assert diet["471376"] == ("FREE_FROM_GLUTEN", "VEGAN")
    assert diet["463968"] == ()


def test_learn_needs_four_weeks(history):
    short = replace(history, weeks=history.weeks[:3])
    with pytest.raises(NotEnoughHistory):
        learn(short)
    assert learn(replace(history, weeks=history.weeks[:4])).learned_from == 4


def test_history_marked_simulated(so):
    assert so.simulated is True


# --- Drift Watch ---


def test_next_four_renewals_from_saturday(so):
    assert next_renewals(so.weekday, NOW, 4) == [date(2026, 11, 16), date(2026, 11, 23),
                                                 date(2026, 11, 30), date(2026, 12, 7)]


@pytest.fixture(scope="module")
def flags(so, history, catalog, valio):
    quotes, avail, _ = fetch(so, catalog, valio, NOW, stockout=False)
    return detect(so, history, quotes, avail, NOW, catalog)


def test_mozzarella_per_guest_flag_26pct(flags):
    f = [x for x in flags if x.kind is DriftKind.PER_GUEST_UP]
    assert [x.product_id for x in f] == ["466375"]
    assert f[0].pct == 26  # (116 + 120) / 2 = 118 against (92 + 92 + 94 + 96) / 4 = 93.5
    assert "26 % more" in f[0].sentence and "118" in f[0].sentence and "93.5" in f[0].sentence


def test_flat_lines_have_no_per_guest_flag(flags):
    assert {x.product_id for x in flags if x.kind is DriftKind.PER_GUEST_UP} == {"466375"}


def test_stock_below_for_parmesan_and_pancakes(flags):
    below = {x.product_id: x.value for x in flags if x.kind is DriftKind.STOCK_BELOW}
    assert below == {"463968": 137, "471376": 27}


def test_464306_contract_ends_after_the_next_four_renewals(flags):
    # 1.01 EUR until 31 Dec, the 4th renewal is 7 Dec: no flag yet
    assert not [x for x in flags if x.kind is DriftKind.CONTRACT_ENDS]


def test_contract_ends_flag_before_fourth_renewal(so, history, catalog, valio):
    quotes, avail, _ = fetch(so, catalog, valio, NOW, stockout=False)
    quotes["464306"] = replace(quotes["464306"], valid_to=date(2026, 12, 1))
    f = [x for x in detect(so, history, quotes, avail, NOW, catalog) if x.kind is DriftKind.CONTRACT_ENDS]
    assert [x.product_id for x in f] == ["464306"]
    assert "1 Dec" in f[0].sentence


def test_cost_up_over_ten_pct(so, history, catalog, valio):
    quotes, avail, _ = fetch(so, catalog, valio, NOW, stockout=False)
    paid = [replace(w, unit_cents={"464306": 91}) for w in history.weeks]  # 1.01 is 11 % over 0.91
    f = detect(so, replace(history, weeks=paid), quotes, avail, NOW, catalog)
    assert [(x.product_id, x.pct) for x in f if x.kind is DriftKind.COST_UP] == [("464306", 11)]
    paid = [replace(w, unit_cents={"464306": 93}) for w in history.weeks]  # 8.6 % over: no flag
    f = detect(so, replace(history, weeks=paid), quotes, avail, NOW, catalog)
    assert not [x for x in f if x.kind is DriftKind.COST_UP]


def test_per_guest_flag_threshold_is_20pct(so, catalog, valio):
    def hist(last):
        weeks = [PastOrder(date(2026, 9, 21) + timedelta(weeks=i), 400, {"464306": q}, True)
                 for i, q in enumerate([100, 100, 100, 100, 100, 100, last, last])]
        return History("hotel-espoo", 0, {"464306": ("FREE_FROM_LACTOSE",)}, weeks, True)

    quotes, avail, _ = fetch(so, catalog, valio, NOW, stockout=False)
    for last, flagged in [(120, False), (121, True)]:
        h = hist(last)
        f = detect(learn(h), h, quotes, avail, NOW, catalog)
        assert bool([x for x in f if x.kind is DriftKind.PER_GUEST_UP]) is flagged, last


def test_per_guest_uses_guests_not_amount(so, catalog, valio):
    # more bags but also more guests: per guest unchanged, no flag
    weeks = [PastOrder(date(2026, 9, 21) + timedelta(weeks=i), g, {"464306": q}, True)
             for i, (g, q) in enumerate([(400, 100)] * 4 + [(600, 150)] * 2)]
    h = History("hotel-espoo", 0, {"464306": ("FREE_FROM_LACTOSE",)}, weeks, True)
    quotes, avail, _ = fetch(so, catalog, valio, NOW, stockout=False)
    assert not [x for x in detect(learn(h), h, quotes, avail, NOW, catalog) if x.kind is DriftKind.PER_GUEST_UP]


# --- renewal ---


def test_flat_lines_renew_alone(renewal):
    milk = line(renewal, "464306")
    assert milk.result is LineResult.RENEWED
    assert (milk.this_week_qty, milk.total_cents) == (300, 30300)
    assert milk.decision.outcome == "allow"


def test_parmesan_partial_split_renews_alone(renewal):
    p = line(renewal, "463968")
    assert p.result is LineResult.SPLIT_RENEWED
    assert [(x.product.id, x.sales_qty) for x in p.split.parts] == [("463968", 137), ("469648", 40)]
    assert p.total_cents == 77249
    assert p.decision.outcome == "allow"
    assert "18.49" in p.sentence and "2.5 %" in p.sentence


def test_pancakes_wait_for_human(renewal):
    p = line(renewal, "471376")
    assert p.result is LineResult.WAITING
    assert p.this_week_qty == 27
    assert "wheat" in p.sentence and "27 of 30" in p.sentence
    assert p.accept_label == "Order 27 now"


def test_mozzarella_waits_with_its_flag(renewal):
    m = line(renewal, "466375")
    assert m.result is LineResult.FLAGGED
    assert [f.kind for f in m.flags] == [DriftKind.PER_GUEST_UP]
    assert m.decision.outcome == "escalate"
    assert "Drift Watch flagged this line" in m.decision.sentence
    assert m.accept_label == "Renew anyway"


def test_flagged_lines_never_reach_split_fill(so, history, catalog, valio, mandate):
    rec = Recorder()
    run(so, history, catalog, valio, mandate, NOW, stockout=True, split_fill=rec)
    assert rec.asked == ["463968", "471376"]
    assert "466375" not in rec.asked  # flagged for drift first, the stock-out only adds a second flag


def test_stockout_adds_stock_flag_to_mozzarella(so, history, catalog, valio, mandate):
    r = run(so, history, catalog, valio, mandate, NOW, stockout=True)
    kinds = [f.kind for f in line(r, "466375").flags]
    assert kinds == [DriftKind.PER_GUEST_UP, DriftKind.STOCK_BELOW]


def test_renewal_stays_within_call_budget(so, catalog, valio):
    _, _, budget = fetch(so, catalog, valio, NOW, stockout=False)
    assert 0 < budget.ids_sent <= 40


def test_accept_lets_a_waiting_line_through(renewal):
    r = accept(renewal, "471376", approver="chef")
    assert line(r, "471376").result is LineResult.ACCEPTED
    assert line(renewal, "471376").result is LineResult.WAITING  # the original is unchanged


def test_accept_refuses_a_line_that_renewed_alone(renewal):
    with pytest.raises(ValueError):
        accept(renewal, "464306", approver="chef")


def test_without_split_fill_partial_lines_wait(so, history, catalog, valio, mandate):
    r = run(so, history, catalog, valio, mandate, NOW, stockout=False, split_fill=lambda *a: None)
    assert line(r, "463968").result is LineResult.WAITING
    assert line(r, "464306").result is LineResult.RENEWED


def test_split_over_limit_waits(so, history, catalog, valio, mandate):
    tight = replace(mandate, split_max_extra_bp=200)  # the split costs 2.5 % more, over a 2 % limit
    r = run(so, history, catalog, valio, tight, NOW, stockout=False)
    p = line(r, "463968")
    assert p.result is LineResult.WAITING
    assert "split limit" in p.sentence and p.this_week_qty == 137


def test_price_comes_from_valio_not_history(so, history, catalog, valio, mandate):
    q = Quote("464306", False, 150, None, True, None, None, None, None)
    quotes, avail, _ = fetch(so, catalog, valio, NOW, stockout=False)
    quotes["464306"] = q
    r = renew(so, detect(so, history, quotes, avail, NOW, catalog), catalog, quotes, avail, mandate, NOW)
    assert line(r, "464306").total_cents == 300 * 150


# review-3 H4: Valio has 36 ST of 469054, that is 3 cartons of 12. Drift and renew count cartons.


def _one_line(pid, qty):
    from validio.standing.model import StandingLine, StandingOrder

    return StandingOrder("SO-T", "hotel-espoo", "test", 0, [StandingLine(pid, qty, 0.0, ())], 200, 8, True)


def test_drift_counts_stock_in_sales_units(history, catalog, valio):
    so1 = _one_line("469054", 10)
    quotes, avail, _ = fetch(so1, catalog, valio, NOW, stockout=False)
    (f,) = [x for x in detect(so1, history, quotes, avail, NOW, catalog) if x.kind is DriftKind.STOCK_BELOW]
    assert f.sentence == "Only 3 cartons in stock, the usual line is 10."
    assert not [x for x in detect(_one_line("469054", 3), history, quotes, avail, NOW, catalog)
                if x.kind is DriftKind.STOCK_BELOW]  # control: 3 cartons cover 3


def test_renew_offers_stock_in_sales_units(history, catalog, valio, mandate):
    so1 = _one_line("469054", 10)
    quotes, avail, _ = fetch(so1, catalog, valio, NOW, stockout=False)
    r = renew(so1, detect(so1, history, quotes, avail, NOW, catalog), catalog, quotes, avail, mandate, NOW,
              split_fill=lambda *a, **k: None)
    (ln,) = r.lines
    assert ln.this_week_qty == 3
    assert ln.accept_label == "Order 3 now"
