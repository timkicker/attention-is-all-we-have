"""Step 7, Open Ledger: the chain verifies, one changed entry is caught, the approver list never appears."""

import json
import sqlite3
from datetime import datetime
from itertools import pairwise

from validio.audit.log import GENESIS, AuditLog, entry_hash
from validio.audit.sentences import ordered_alone

NOW = datetime.fromisoformat("2026-11-14T10:00:00+02:00")

# What the agent disclosed for scene 2 (Spend Pass M-1), plus approvers to prove they are dropped.
DISCLOSED = {"autoLimitCents": 120000, "hardCapCents": 200000, "diet": ["FREE_FROM_LACTOSE"]}


def _fill(log: AuditLog, n: int = 3) -> None:
    for i in range(n):
        log.append(
            at=NOW,
            actor="agent:buyer-1",
            kind="decision",
            sentence=f"entry {i}",
            facts=[{"field": "quantity", "value": 1000, "grade": "attested", "source": "Valio"}],
            mandate_id="M-1",
            disclosed=DISCLOSED,
            rule_ids=["auto-order"],
            order_id=f"O-{i}",
        )


def test_chain_verifies(tmp_path):
    log = AuditLog(tmp_path / "ledger.db")
    _fill(log, 5)
    result = log.verify()
    assert result.ok
    assert result.count == 5
    assert result.broken_at is None
    entries = log.list()
    assert [e.seq for e in entries] == [1, 2, 3, 4, 5]
    assert entries[0].prev_hash == GENESIS
    for prev, cur in pairwise(entries):
        assert cur.prev_hash == prev.hash


def test_empty_ledger_verifies(tmp_path):
    result = AuditLog(tmp_path / "ledger.db").verify()
    assert result.ok and result.count == 0


def test_hash_is_sha256_over_sorted_compact_json(tmp_path):
    import hashlib

    log = AuditLog(tmp_path / "ledger.db")
    _fill(log, 1)
    e = log.list()[0]
    body = {k: v for k, v in e.as_dict().items() if k != "hash"}
    expected = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert e.hash == expected == entry_hash(body)


def test_tamper_detected(tmp_path):
    path = tmp_path / "ledger.db"
    log = AuditLog(path)
    _fill(log, 5)
    # one changed letter in entry 3, written straight into the database
    con = sqlite3.connect(path)
    body = con.execute("SELECT body FROM ledger WHERE seq = 3").fetchone()[0]
    con.execute("UPDATE ledger SET body = ? WHERE seq = 3", (body.replace("entry 2", "entry X"),))
    con.commit()
    con.close()
    result = AuditLog(path).verify()
    assert not result.ok
    assert result.broken_at == 3


def test_tamper_with_recomputed_hash_caught_at_next(tmp_path):
    path = tmp_path / "ledger.db"
    log = AuditLog(path)
    _fill(log, 5)
    con = sqlite3.connect(path)
    body = json.loads(con.execute("SELECT body FROM ledger WHERE seq = 2").fetchone()[0])
    body["sentence"] = "nothing happened"
    new_hash = entry_hash(body)
    con.execute(
        "UPDATE ledger SET body = ?, hash = ? WHERE seq = 2",
        (json.dumps(body, sort_keys=True, separators=(",", ":")), new_hash),
    )
    con.commit()
    con.close()
    result = AuditLog(path).verify()
    assert not result.ok
    assert result.broken_at == 3


def test_deleted_entry_caught(tmp_path):
    path = tmp_path / "ledger.db"
    log = AuditLog(path)
    _fill(log, 4)
    con = sqlite3.connect(path)
    con.execute("DELETE FROM ledger WHERE seq = 2")
    con.commit()
    con.close()
    result = AuditLog(path).verify()
    assert not result.ok
    assert result.broken_at == 3


def test_undisclosed_claims_never_logged(tmp_path):
    path = tmp_path / "ledger.db"
    log = AuditLog(path)
    log.append(
        at=NOW,
        actor="agent:buyer-1",
        kind="decision",
        sentence="s",
        facts=[],
        mandate_id="M-1",
        disclosed={**DISCLOSED, "approvers": ["owner:anna"]},
        rule_ids=["auto-order"],
        order_id="O-1",
    )
    e = log.list()[0]
    assert "approvers" not in e.disclosed
    assert e.disclosed == DISCLOSED
    raw = path.read_bytes()
    assert b"owner:anna" not in raw
    assert b"approvers" not in raw
    assert log.verify().ok


def test_list_by_order(tmp_path):
    log = AuditLog(tmp_path / "ledger.db")
    _fill(log, 3)
    assert [e.order_id for e in log.list(order_id="O-1")] == ["O-1"]


def test_sentence_scene2_exact():
    s = ordered_alone(
        quantity=1000,
        unit="ST",
        product_id="464306",
        product_name="Valio Arki® Eila® 1 L",
        total_cents=101000,
        price_valid_until="2026-12-31",
        delivery_date="2026-11-16",
        mandate_id="M-1",
        auto_limit_cents=120000,
    )
    assert s == (
        "Ordered 1,000 pieces of Valio Arki Eila 1 l for 1,010.00 € without a person. "
        "Valio attests the stock and the contract price until 31 Dec 2026, delivery 16 Nov. "
        "Inside Spend Pass M-1, whose disclosed auto limit is 1,200.00 €."
    )


# The head (count and last hash) lives outside the chain, so a cut at the end is caught too (review M3).


def _sql(path, *stmts):
    con = sqlite3.connect(path)
    for s in stmts:
        con.execute(s)
    con.commit()
    con.close()


def test_deleted_last_entry_caught(tmp_path):
    path = tmp_path / "ledger.db"
    _fill(AuditLog(path), 3)
    _sql(path, "DELETE FROM ledger WHERE seq = 3")
    result = AuditLog(path).verify()
    assert not result.ok
    assert result.broken_at == 3


def test_emptied_ledger_caught(tmp_path):
    path = tmp_path / "ledger.db"
    _fill(AuditLog(path), 3)
    _sql(path, "DELETE FROM ledger")
    result = AuditLog(path).verify()
    assert not result.ok
    assert result.broken_at == 1


def test_deleted_head_caught(tmp_path):
    path = tmp_path / "ledger.db"
    _fill(AuditLog(path), 3)
    _sql(path, "DELETE FROM ledger_head")
    assert not AuditLog(path).verify().ok


def test_edited_order_id_column_caught(tmp_path):
    path = tmp_path / "ledger.db"
    log = AuditLog(path)
    _fill(log, 3)
    _sql(path, "UPDATE ledger SET order_id = 'O-0' WHERE seq = 2")
    result = AuditLog(path).verify()
    assert not result.ok
    assert result.broken_at == 2


def test_head_follows_appends(tmp_path):
    path = tmp_path / "ledger.db"
    log = AuditLog(path)
    _fill(log, 2)
    assert log.verify() == (True, 2, None)
    _fill(log, 1)
    assert AuditLog(path).verify() == (True, 3, None)


def test_ledger_from_before_the_head_is_adopted(tmp_path):
    # a ledger written before the head table existed verifies once, then is anchored like any other
    path = tmp_path / "ledger.db"
    _fill(AuditLog(path), 3)
    _sql(path, "DROP TABLE ledger_head")
    assert AuditLog(path).verify() == (True, 3, None)
    _sql(path, "DELETE FROM ledger WHERE seq = 3")
    assert not AuditLog(path).verify().ok


def test_hash_keeps_non_ascii_as_utf8(tmp_path):
    # the hash is over UTF-8 with the letters as they are (ensure_ascii=False), not over escaped ASCII
    import hashlib

    log = AuditLog(tmp_path / "ledger.db")
    e = log.append(at=NOW, actor="validio", kind="decision", sentence="Hyvää Suomesta label shown", facts=[],
                   mandate_id="M-1", disclosed={}, rule_ids=[], order_id="O-1")
    body = {k: v for k, v in e.as_dict().items() if k != "hash"}
    text = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert "Hyvää" in text
    assert e.hash == hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert e.hash != hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
