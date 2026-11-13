"""Open Ledger: one entry per decision, each chained to the one before by its SHA-256 hash.

The hash is SHA-256 over the entry as JSON with sorted keys and no spaces, without the hash itself.
Hidden Spend Pass fields such as the approver list are dropped before anything is written.
"""

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, NamedTuple

GENESIS = "0" * 64

# Spend Pass fields that never enter the ledger, even when an agent discloses them.
NEVER_LOGGED = frozenset({"approvers"})

SCHEMA = """
CREATE TABLE IF NOT EXISTS ledger (
  seq INTEGER PRIMARY KEY,
  order_id TEXT,
  body TEXT NOT NULL,
  hash TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ledger_order ON ledger(order_id);
"""


def canonical(body: dict[str, Any]) -> str:
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def entry_hash(body: dict[str, Any]) -> str:
    return hashlib.sha256(canonical(body).encode()).hexdigest()


@dataclass(frozen=True)
class AuditEntry:
    seq: int
    at: str
    actor: str
    kind: str
    sentence: str
    facts: list[dict[str, Any]]
    mandate_id: str | None
    disclosed: dict[str, Any]
    rule_ids: list[str]
    order_id: str | None
    prev_hash: str
    hash: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class VerifyResult(NamedTuple):
    ok: bool
    count: int
    broken_at: int | None  # seq of the first entry that does not check out


class AuditLog:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False)
        self._con.executescript(SCHEMA)

    def append(
        self,
        *,
        at: datetime,
        actor: str,
        kind: str,
        sentence: str,
        facts: list[dict[str, Any]],
        mandate_id: str | None,
        disclosed: dict[str, Any],
        rule_ids: list[str],
        order_id: str | None,
    ) -> AuditEntry:
        con = self._con
        con.execute("BEGIN IMMEDIATE")
        try:
            row = con.execute("SELECT seq, hash FROM ledger ORDER BY seq DESC LIMIT 1").fetchone()
            seq, prev = (row[0] + 1, row[1]) if row else (1, GENESIS)
            body = {
                "seq": seq,
                "at": at.isoformat(),
                "actor": actor,
                "kind": kind,
                "sentence": sentence,
                "facts": facts,
                "mandate_id": mandate_id,
                "disclosed": {k: v for k, v in disclosed.items() if k not in NEVER_LOGGED},
                "rule_ids": list(rule_ids),
                "order_id": order_id,
                "prev_hash": prev,
            }
            # round trip so the stored body is exactly what gets hashed
            body = json.loads(canonical(body))
            h = entry_hash(body)
            con.execute(
                "INSERT INTO ledger (seq, order_id, body, hash) VALUES (?, ?, ?, ?)",
                (seq, order_id, canonical(body), h),
            )
            con.execute("COMMIT")
        except BaseException:
            con.execute("ROLLBACK")
            raise
        return AuditEntry(**body, hash=h)

    def list(self, order_id: str | None = None) -> list[AuditEntry]:
        if order_id is None:
            rows = self._con.execute("SELECT body, hash FROM ledger ORDER BY seq").fetchall()
        else:
            rows = self._con.execute(
                "SELECT body, hash FROM ledger WHERE order_id = ? ORDER BY seq", (order_id,)
            ).fetchall()
        return [AuditEntry(**json.loads(b), hash=h) for b, h in rows]

    def verify(self) -> VerifyResult:
        prev = GENESIS
        count = 0
        expected_seq = 1
        for stored_seq, body_text, h in self._con.execute("SELECT seq, body, hash FROM ledger ORDER BY seq"):
            try:
                body = json.loads(body_text)
            except ValueError:
                return VerifyResult(False, count, stored_seq)
            if (
                stored_seq != expected_seq
                or body.get("seq") != stored_seq
                or body.get("prev_hash") != prev
                or entry_hash(body) != h
            ):
                return VerifyResult(False, count, stored_seq)
            prev = h
            count += 1
            expected_seq += 1
        return VerifyResult(True, count, None)
