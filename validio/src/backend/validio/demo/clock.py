"""The demo clock. The demo runs at a fixed moment (VALIDIO_NOW, 10:00). Every ledger entry moves it on by a few
minutes, so the times on the screens tell the story in order. It counts the entries, so a reset brings it back
to 10:00 and every run shows the same times. A step stays under the nonce lifetime of five minutes."""

import sqlite3
from datetime import datetime, timedelta

STEPS = (2, 3, 4, 2, 3)  # minutes per ledger entry, in turn


def offset(entries: int) -> timedelta:
    full, rest = divmod(entries, len(STEPS))
    return timedelta(minutes=full * sum(STEPS) + sum(STEPS[:rest]))


def demo_now(base: datetime, con: sqlite3.Connection) -> datetime:
    try:
        (n,) = con.execute("select count(*) from ledger").fetchone()
    except sqlite3.OperationalError:  # no ledger yet
        n = 0
    return base + offset(n)
