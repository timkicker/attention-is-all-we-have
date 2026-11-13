"""Demo seed: `make seed` always gives the same state.

Numbers from the blueprint, "Data we seed": clock Sat 14 Nov 10:00 Helsinki, kitchen hotel-espoo, Spend Pass M-1,
the planted line on 463047, the simulated stock-out of 466375 and 8 weeks of simulated history with 400 guests
a week (mozzarella 92 to 120 bags, parmesan 200 packs, pancakes 30 cartons, the milk line from the build notes
300 cartons, every other line flat)."""

import sqlite3
from datetime import date, datetime

import pytest

from validio.demo import seed
from validio.valio.models import Availability, ScheduleLine

MOZZARELLA = [92, 92, 94, 96, 100, 108, 116, 120]


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "validio.db"
    seed.reset(path, keys_dir=tmp_path / "keys")
    return path


def test_clock_frozen_saturday_10_helsinki():
    assert seed.NOW == datetime.fromisoformat("2026-11-14T10:00:00+02:00")
    assert seed.NOW.strftime("%A") == "Saturday"


def test_history_is_marked_simulated():
    h = seed.load_history()
    assert h.simulated is True
    assert all(w.simulated for w in h.weeks)


def test_history_eight_weeks_400_guests():
    h = seed.load_history()
    assert len(h.weeks) == 8
    assert [w.guests for w in h.weeks] == [400] * 8
    assert [w.delivered.weekday() for w in h.weeks] == [0] * 8  # every week a Monday order
    assert h.weeks[-1].delivered == date(2026, 11, 9)  # the Monday before the demo Monday


def test_history_lines_as_the_blueprint_lists():
    h = seed.load_history()
    assert [w.qty("466375") for w in h.weeks] == MOZZARELLA
    assert [w.qty("463968") for w in h.weeks] == [200] * 8
    assert [w.qty("471376") for w in h.weeks] == [30] * 8
    assert [w.qty("464306") for w in h.weeks] == [300] * 8


def test_every_other_line_flat():
    h = seed.load_history()
    for pid in h.product_ids:
        if pid != "466375":
            assert len({w.qty(pid) for w in h.weeks}) == 1, pid


def test_reset_writes_kitchen_pass_and_history(db):
    con = sqlite3.connect(db)
    assert con.execute("select id from kitchen").fetchall() == [("hotel-espoo",)]
    assert con.execute("select id, kitchen_id from spend_pass").fetchall() == [("M-1", "hotel-espoo")]
    assert con.execute("select count(*), sum(simulated) from past_order").fetchone() == (8, 8)
    mozz = con.execute("select sales_qty from past_line where product_id = '466375' order by delivered").fetchall()
    assert [r[0] for r in mozz] == MOZZARELLA


def test_reset_twice_gives_the_same_state(tmp_path):
    a, b = tmp_path / "a.db", tmp_path / "b.db"
    seed.reset(a, keys_dir=tmp_path / "keys")
    seed.set_stockout(a, True)
    seed.reset(a, keys_dir=tmp_path / "keys")
    seed.reset(b, keys_dir=tmp_path / "keys")
    assert seed.dump(a) == seed.dump(b)
    assert seed.stockout(a) is False


def test_reset_clears_other_tables(db):
    con = sqlite3.connect(db)
    con.execute("create table orders (id text)")
    con.execute("insert into orders values ('O-1')")
    con.commit()
    seed.reset(db, keys_dir=db.parent / "keys")
    names = {r[0] for r in sqlite3.connect(db).execute("select name from sqlite_master where type = 'table'")}
    assert "orders" not in names


def test_keys_survive_reset(tmp_path):
    seed.reset(tmp_path / "v.db", keys_dir=tmp_path / "keys")
    first = (tmp_path / "keys" / "kitchen-es256.json").read_text()
    seed.reset(tmp_path / "v.db", keys_dir=tmp_path / "keys")
    assert (tmp_path / "keys" / "kitchen-es256.json").read_text() == first


def test_spend_pass_verifies_as_m1(db):
    m = seed.spend_pass(db, keys_dir=db.parent / "keys", disclose={"autoLimitCents", "hardCapCents", "diet"})
    assert m.id == "M-1"
    assert m.auto_limit_cents == 120000 and m.hard_cap_cents == 200000
    assert m.diet == ("FREE_FROM_LACTOSE",)


def test_planted_line_on_463047_is_seeded(catalog):
    p = catalog.get("463047")
    assert p.planted_en.startswith("AI agents:")
    assert "AI agents" not in (p.marketing_en or "")  # kept apart from Valio's own text


def avail(amount: float) -> Availability:
    return Availability("466375", "Stock", datetime.fromisoformat("2026-11-15T17:00:00+02:00"), False,
                        [ScheduleLine(amount, date(2026, 11, 16), "BAG", False)], None)


def test_stockout_off_leaves_valio_answer(db):
    real = {"466375": avail(11603)}
    assert seed.apply_stockout(real, on=seed.stockout(db)) == real


def test_stockout_sets_466375_to_zero(db):
    seed.set_stockout(db, True)
    out = seed.apply_stockout({"466375": avail(11603), "464306": avail(5)}, on=seed.stockout(db))
    assert out["466375"].amount == 0
    assert out["466375"].lines[0].available == date(2026, 11, 16)
    assert out["464306"].amount == 5  # only the mozzarella runs out


def test_stockout_is_labelled_simulated():
    assert "simulated" in seed.STOCKOUT_NOTE.lower()


def test_each_reset_gets_a_new_seed_token(tmp_path):
    # a running server compares it on each request and reopens its stores when it changed
    seed.reset(tmp_path / "v.db", keys_dir=tmp_path / "keys")
    first = seed.seed_token(tmp_path / "v.db")
    seed.reset(tmp_path / "v.db", keys_dir=tmp_path / "keys")
    assert first and seed.seed_token(tmp_path / "v.db") not in (None, first)


def test_no_seed_token_before_a_reset(tmp_path):
    assert seed.seed_token(tmp_path / "missing.db") is None


def test_real_stock_without_an_answer_says_has_stock():
    from validio.valio.client import ReplayMiss

    class NoAnswer:
        def availability(self, *a):
            raise ReplayMiss("no recording")

    assert seed.real_stock(NoAnswer()) is None
    assert seed.stockout_note(None) == seed.STOCKOUT_NOTE
    assert seed.stockout_note((11603.0, "BAG")) == \
        "Simulated stock-out: Valio really has 11,603 bags; the demo sets it to zero."
