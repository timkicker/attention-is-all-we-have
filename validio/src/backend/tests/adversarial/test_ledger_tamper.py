"""Open Ledger tamper matrix: someone with write access to validio.db edits, deletes, reorders, inserts or
truncates entries, or changes an order id or a timestamp. verify() must say the chain is broken, at the
right place, and the web app must still answer with that verdict."""

import json
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from validio.audit.log import GENESIS, AuditLog, canonical, entry_hash

T0 = datetime.fromisoformat("2026-11-14T10:00:00+02:00")
N = 6


def fill(path) -> AuditLog:
    log = AuditLog(path)
    for i in range(1, N + 1):
        log.append(at=T0 + timedelta(minutes=i), actor="validio", kind="decision", sentence=f"Decision {i}.",
                   facts=[{"field": "price", "value": f"{i}.00 EUR", "grade": "attested"}], mandate_id="M-1",
                   disclosed={"autoLimitCents": 120000}, rule_ids=["auto-order"], order_id=f"O-{(i + 1) // 2}")
    assert log.verify() == (True, N, None)
    return log


def rows(con):
    return con.execute("select seq, order_id, body, hash from ledger order by seq").fetchall()


def body_of(con, seq):
    return json.loads(con.execute("select body from ledger where seq = ?", (seq,)).fetchone()[0])


def put(con, seq, body, rehash=False, order_id=None):
    text = canonical(body)
    if rehash:
        con.execute("update ledger set body = ?, hash = ? where seq = ?", (text, entry_hash(body), seq))
    else:
        con.execute("update ledger set body = ? where seq = ?", (text, seq))
    if order_id is not None:
        con.execute("update ledger set order_id = ? where seq = ?", (order_id, seq))


def edit(field, value, rehash=False, seq=3):
    def go(con):
        b = body_of(con, seq)
        b[field] = value
        put(con, seq, b, rehash)
    return go


def delete(seq):
    return lambda con: con.execute("delete from ledger where seq = ?", (seq,))


def swap(a, b):
    def go(con):
        ra, rb = (con.execute("select order_id, body, hash from ledger where seq = ?", (s,)).fetchone() for s in (a, b))
        for seq, r in ((a, rb), (b, ra)):
            con.execute("update ledger set order_id = ?, body = ?, hash = ? where seq = ?", (*r, seq))
    return go


def swap_renumbered(a, b):
    """Swap two entries and fix seq and prev_hash inside each body, rehashing both."""
    def go(con):
        ba, bb = body_of(con, a), body_of(con, b)
        ba["seq"], bb["seq"] = b, a
        ba["prev_hash"], bb["prev_hash"] = bb["prev_hash"], ba["prev_hash"]
        put(con, a, bb, rehash=True, order_id=bb["order_id"])
        put(con, b, ba, rehash=True, order_id=ba["order_id"])
    return go


def insert_middle(con):
    for seq, *_ in reversed(rows(con)):
        if seq >= 3:
            con.execute("update ledger set seq = seq + 1 where seq = ?", (seq,))
    prev = con.execute("select hash from ledger where seq = 2").fetchone()[0]
    b = {**body_of(con, 2), "seq": 3, "sentence": "Owner approved 9999 ST.", "prev_hash": prev}
    con.execute("insert into ledger values (3, ?, ?, ?)", (b["order_id"], canonical(b), entry_hash(b)))


def append_forged(con):
    last = rows(con)[-1]
    b = {**json.loads(last[2]), "seq": last[0] + 1, "sentence": "Owner approved 9999 ST.", "prev_hash": last[3]}
    con.execute("insert into ledger values (?, ?, ?, ?)", (b["seq"], b["order_id"], canonical(b), entry_hash(b)))


def set_order_column(con):
    con.execute("update ledger set order_id = 'O-99' where seq = 3")


def order_id_everywhere(con):
    b = body_of(con, 3)
    b["order_id"] = "O-99"
    put(con, 3, b, rehash=True, order_id="O-99")


def raw_body(text, seq=3):
    return lambda con: con.execute("update ledger set body = ? where seq = ?", (text, seq))


MATRIX = {
    # name: (tamper, first broken seq)
    "edit sentence": (edit("sentence", "Decision 3, approved by nobody."), 3),
    "edit sentence and rehash": (edit("sentence", "Decision 3, approved by nobody.", rehash=True), 4),
    "edit last entry and rehash": (edit("sentence", "x", rehash=True, seq=N), N),
    "edit first entry and rehash": (edit("sentence", "x", rehash=True, seq=1), 2),
    "edit fact value": (edit("facts", [{"field": "price", "value": "0.01 EUR", "grade": "attested"}]), 3),
    "add approvers to disclosed": (edit("disclosed", {"autoLimitCents": 120000, "approvers": ["owner:anna"]}), 3),
    "edit rule ids": (edit("rule_ids", ["ask-human"]), 3),
    "edit actor": (edit("actor", "owner"), 3),
    "edit mandate id": (edit("mandate_id", "M-2"), 3),
    "change timestamp": (edit("at", (T0 + timedelta(days=1)).isoformat()), 3),
    "change timestamp and rehash": (edit("at", (T0 - timedelta(days=1)).isoformat(), rehash=True), 4),
    "timestamp as UTC, same instant": (edit("at", (T0 + timedelta(minutes=3)).astimezone(UTC).isoformat()), 3),
    "seq as float in body": (edit("seq", 3.0), 3),
    "prev hash pointed at genesis": (edit("prev_hash", GENESIS, rehash=True), 3),
    "delete first": (delete(1), 2),  # the first row left is the first that fails
    "delete middle": (delete(3), 4),
    "delete last": (delete(N), N),
    "delete two in the middle": (lambda con: con.execute("delete from ledger where seq in (3, 4)"), 5),
    "truncate": (lambda con: con.execute("delete from ledger"), 1),
    "truncate tail": (lambda con: con.execute("delete from ledger where seq > 2"), 3),
    "drop head row": (lambda con: con.execute("delete from ledger_head"), 1),
    "head count changed": (lambda con: con.execute("update ledger_head set count = count + 1"), N + 1),
    "reorder two rows": (swap(2, 3), 2),
    "reorder and renumber": (swap_renumbered(2, 3), 3),  # row 2 rechains cleanly
    "reorder by seq column": (lambda con: con.executescript(
        "update ledger set seq = -1 where seq = 2; update ledger set seq = 2 where seq = 3;"
        "update ledger set seq = 3 where seq = -1;"), 2),
    "insert in the middle": (insert_middle, 4),  # the forged row itself chains
    "append without the head": (append_forged, N + 1),
    "order id column only": (set_order_column, 3),
    "order id in body only": (edit("order_id", "O-99"), 3),
    "order id in body and column, rehashed": (order_id_everywhere, 4),
    "body not json": (raw_body("{not json"), 3),
    "hash column emptied": (lambda con: con.execute("update ledger set hash = '' where seq = 3"), 3),
}


G9 = pytest.mark.xfail(strict=True, reason="review-2 G9: an entry appended past the head is reported at the last "
                                           "honest seq, not at the forged one")
CASES = [pytest.param(n, marks=G9) if n == "append without the head" else n for n in MATRIX]


@pytest.mark.parametrize("name", CASES)
def test_tamper_is_caught(tmp_path, name):
    tamper, at = MATRIX[name]
    path = tmp_path / "validio.db"
    fill(path).verify()
    con = sqlite3.connect(path, isolation_level=None)
    tamper(con)
    con.close()
    ok, _count, broken_at = AuditLog(path).verify()
    assert not ok, f"{name} not caught"
    assert broken_at == at, f"{name}: broken at {broken_at}, expected {at}"


# Bodies that are valid JSON but not an object: verify must say "broken", not crash.

@pytest.mark.xfail(strict=True, reason="review-2 G6: verify() raises AttributeError on a body that is JSON but not "
                                       "an object, so /api/ledger answers 500 instead of chain.ok false")
@pytest.mark.parametrize("text", ["[]", "null", "42", '"x"'])
def test_body_that_is_not_an_object_is_caught(tmp_path, text):
    path = tmp_path / "validio.db"
    fill(path)
    con = sqlite3.connect(path, isolation_level=None)
    raw_body(text)(con)
    con.close()
    assert AuditLog(path).verify() == (False, 2, 3)


# A full rewrite including the head is beyond what one file can prove (module docstring of audit/log.py).

def _rewrite_all(con, keep=lambda seq: True, change=lambda b: b):
    prev, n = GENESIS, 0
    old = [(s, json.loads(b)) for s, _, b, _ in rows(con) if keep(s)]
    con.execute("delete from ledger")
    for _seq, b in old:
        n += 1
        b = change({**b, "seq": n, "prev_hash": prev})
        h = entry_hash(b)
        con.execute("insert into ledger values (?, ?, ?, ?)", (n, b["order_id"], canonical(b), h))
        prev = h
    con.execute("update ledger_head set count = ?, hash = ?", (n, prev))


@pytest.mark.xfail(strict=True, reason="review-2 G7 (known limit): a rewrite of every row and the head is not "
                                       "caught; needs the head published or signed outside validio.db")
@pytest.mark.parametrize("how", ["drop seq 3 and rechain", "edit and rechain", "empty with head reset"])
def test_full_rewrite_with_head_is_caught(tmp_path, how):
    path = tmp_path / "validio.db"
    fill(path)
    con = sqlite3.connect(path, isolation_level=None)
    if how == "drop seq 3 and rechain":
        _rewrite_all(con, keep=lambda s: s != 3)
    elif how == "edit and rechain":
        _rewrite_all(con, change=lambda b: {**b, "sentence": b["sentence"].replace("3", "9")})
    else:
        con.execute("delete from ledger")
        con.execute("update ledger_head set count = 0, hash = ?", (GENESIS,))
    con.close()
    assert not AuditLog(path).verify().ok


def test_appends_after_tamper_do_not_heal_the_chain(tmp_path):
    """A new honest entry chains to the tampered last hash; the break stays visible."""
    path = tmp_path / "validio.db"
    fill(path)
    con = sqlite3.connect(path, isolation_level=None)
    edit("sentence", "rewritten", seq=3)(con)
    con.close()
    log = AuditLog(path)
    log.append(at=T0, actor="validio", kind="decision", sentence="later", facts=[], mandate_id=None, disclosed={},
               rule_ids=[], order_id=None)
    assert log.verify() == (False, 2, 3)


def test_reopen_does_not_reanchor_a_truncated_ledger(tmp_path):
    """Opening the file again must not rebuild the head from whatever rows are left."""
    path = tmp_path / "validio.db"
    fill(path)
    con = sqlite3.connect(path, isolation_level=None)
    con.execute("delete from ledger where seq > 3")
    con.close()
    for _ in range(2):
        assert AuditLog(path).verify() == (False, 3, 4)


def test_api_ledger_reports_the_break(ctx, monkeypatch):
    """The web app shows the verdict over HTTP, for a value edit and for a deleted row."""
    from fastapi.testclient import TestClient

    from validio.api.app import app

    for i in range(4):
        ctx.audit.append(at=T0, actor="validio", kind="decision", sentence=f"d{i}", facts=[], mandate_id=None,
                         disclosed={}, rule_ids=[], order_id=None)
    con = sqlite3.connect(ctx.db_path, isolation_level=None)
    edit("sentence", "rewritten", seq=2)(con)
    con.close()
    with TestClient(app) as client:
        r = client.get("/api/ledger")
    assert r.status_code == 200
    assert r.json()["chain"] == {"ok": False, "count": 1, "brokenAt": 2}


@pytest.mark.xfail(strict=True, reason="review-2 G8: AuditLog.list() builds AuditEntry(**body), so a row with an "
                                       "added or missing key makes /api/ledger answer 500 instead of showing the break")
@pytest.mark.parametrize("change", ["extra key", "missing key"])
def test_api_ledger_survives_a_body_with_other_keys(ctx, change):
    from fastapi.testclient import TestClient

    from validio.api.app import app

    for i in range(3):
        ctx.audit.append(at=T0, actor="validio", kind="decision", sentence=f"d{i}", facts=[], mandate_id=None,
                         disclosed={}, rule_ids=[], order_id=None)
    con = sqlite3.connect(ctx.db_path, isolation_level=None)
    b = body_of(con, 2)
    if change == "extra key":
        b["approved_by"] = "owner"
    else:
        del b["actor"]
    put(con, 2, b)
    con.close()
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.get("/api/ledger")
    assert r.status_code == 200 and r.json()["chain"]["ok"] is False
