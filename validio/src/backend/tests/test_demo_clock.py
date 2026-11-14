"""The demo clock: 10:00 at a reset, then a few minutes later for every ledger entry, the same on every run."""

import sqlite3
from datetime import datetime, timedelta
from itertools import pairwise

from validio.demo.clock import STEPS, demo_now

BASE = datetime.fromisoformat("2026-11-14T10:00:00+02:00")


def ledger(n: int) -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.execute("create table ledger (seq integer)")
    con.executemany("insert into ledger values (?)", [(i,) for i in range(n)])
    return con


def test_starts_at_the_base_time():
    assert demo_now(BASE, ledger(0)) == BASE


def test_every_entry_moves_it_two_to_seven_minutes_and_runs_repeat():
    times = [demo_now(BASE, ledger(n)) for n in range(12)]
    gaps = [(b - a) / timedelta(minutes=1) for a, b in pairwise(times)]
    assert all(2 <= g <= 7 for g in gaps)
    assert times == [demo_now(BASE, ledger(n)) for n in range(12)]
    assert all(s < 5 for s in STEPS)  # a nonce (5 minutes) survives one entry written in between


def test_no_ledger_table_means_the_base_time():
    assert demo_now(BASE, sqlite3.connect(":memory:")) == BASE
