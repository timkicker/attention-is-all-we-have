"""Open Ledger: one entry per decision, each chained to the one before by its SHA-256 hash.

The hash is SHA-256 over the entry as JSON with sorted keys and no spaces, without the hash itself.
Hidden Spend Pass fields such as the approver list are dropped before anything is written.

The head (entry count, last hash and the time of the last entry) is kept in its own row and moves in the same
transaction as each append, so verify also catches entries cut from the end or an emptied table, not only gaps
in the middle. With the kitchen's key the head is also signed (ES256) on every append and verify checks that
signature, so someone who rewrites every hash and the head row as well is caught unless they hold the key.
GET /api/ledger/head shows the signed head, so Valio can pin it: an older signed head shown again is the one
thing the signature alone cannot tell apart.
"""

import hashlib
import json
import sqlite3
import threading
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, NamedTuple

from jwcrypto.jwk import JWK
from jwcrypto.jws import JWS, InvalidJWSObject, InvalidJWSSignature

GENESIS = "0" * 64
HEAD_TYP = "validio-ledger-head"

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
CREATE TABLE IF NOT EXISTS ledger_head (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  count INTEGER NOT NULL,
  hash TEXT NOT NULL,
  at TEXT,
  sig TEXT
);
"""

FIELDS = ("seq", "at", "actor", "kind", "sentence", "facts", "mandate_id", "disclosed", "rule_ids", "order_id",
          "prev_hash")


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


class Head(NamedTuple):
    count: int
    hash: str
    at: str | None
    signature: str | None  # compact JWS over head_payload(), None without the kitchen's key


def head_payload(count: int, h: str, at: str | None) -> str:
    return canonical({"count": count, "hash": h, "at": at, "typ": HEAD_TYP})


def head_signature_ok(head: Head, public: JWK) -> bool:
    if not head.signature:
        return False
    try:
        jws = JWS()
        jws.deserialize(head.signature)
        jws.verify(public, alg="ES256")
    except (InvalidJWSObject, InvalidJWSSignature, ValueError):
        return False
    return jws.payload.decode() == head_payload(head.count, head.hash, head.at)


class AuditLog:
    def __init__(self, path: Path | str, key: JWK | None = None, con: sqlite3.Connection | None = None,
                 lock: "threading.RLock | None" = None):
        """`key` is the kitchen's private key. With it every append signs the head and verify checks it.
        `con` shares a connection (autocommit) with the order store, so an entry joins its transaction."""
        self.path = Path(path)
        self._key = key
        self.public = JWK.from_json(key.export_public()) if key is not None else None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._con = con or sqlite3.connect(self.path, isolation_level=None, check_same_thread=False)
        # the server's worker threads share this connection: one call at a time, or two BEGINs collide.
        # A shared connection brings its owner's lock (`lock`), so both sides take the same one.
        self._lock = lock or threading.RLock()
        con = self._con
        con.execute("BEGIN IMMEDIATE")
        try:
            had_head = con.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'ledger_head'").fetchone()
            for stmt in SCHEMA.split(";"):
                if stmt.strip():
                    con.execute(stmt)
            cols = {r[1] for r in con.execute("PRAGMA table_info(ledger_head)")}
            for col in ("at", "sig"):
                if col not in cols:  # a head from before the signature: it stays unsigned, so a keyed verify fails
                    con.execute(f"ALTER TABLE ledger_head ADD COLUMN {col} TEXT")
            if not had_head:
                # a new file, or a ledger from before the head existed: anchor what is there now
                row = con.execute("SELECT seq, hash FROM ledger ORDER BY seq DESC LIMIT 1").fetchone()
                count, h = (row[0], row[1]) if row else (0, GENESIS)
                con.execute("INSERT INTO ledger_head (id, count, hash, at, sig) VALUES (1, ?, ?, NULL, ?)",
                            (count, h, self._sign(count, h, None)))
            con.execute("COMMIT")
        except BaseException:
            con.execute("ROLLBACK")
            raise

    def join(self, con: sqlite3.Connection, lock) -> None:
        """Write through `con` (the order store's) and take its `lock` from now on, so an order and its
        entry commit together."""
        if con is not self._con:
            with self._lock:
                self._con.close()
            self._con, self._lock = con, lock

    def _sign(self, count: int, h: str, at: str | None) -> str | None:
        if self._key is None:
            return None
        jws = JWS(head_payload(count, h, at).encode())
        jws.add_signature(self._key, alg="ES256",
                          protected=canonical({"alg": "ES256", "typ": HEAD_TYP, "kid": self._key.thumbprint()}))
        return jws.serialize(compact=True)

    def head(self) -> Head | None:
        with self._lock:
            row = self._con.execute("SELECT count, hash, at, sig FROM ledger_head WHERE id = 1").fetchone()
        return Head(*row) if row else None

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
        with self._lock:
            return self._append(at=at, actor=actor, kind=kind, sentence=sentence, facts=facts,
                                mandate_id=mandate_id, disclosed=disclosed, rule_ids=rule_ids, order_id=order_id)

    def _append(self, *, at, actor, kind, sentence, facts, mandate_id, disclosed, rule_ids, order_id) -> AuditEntry:
        con = self._con
        nested = con.in_transaction  # inside the order store's transaction: commit or roll back with it
        con.execute("SAVEPOINT ledger_append" if nested else "BEGIN IMMEDIATE")
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
            con.execute("INSERT OR REPLACE INTO ledger_head (id, count, hash, at, sig) VALUES (1, ?, ?, ?, ?)",
                        (seq, h, body["at"], self._sign(seq, h, body["at"])))
            con.execute("RELEASE ledger_append" if nested else "COMMIT")
        except BaseException:
            if nested:
                con.execute("ROLLBACK TO ledger_append")
                con.execute("RELEASE ledger_append")
            else:
                con.execute("ROLLBACK")
            raise
        return AuditEntry(**body, hash=h)

    def list(self, order_id: str | None = None) -> list[AuditEntry]:
        with self._lock:
            if order_id is None:
                rows = self._con.execute("SELECT body, hash FROM ledger ORDER BY seq").fetchall()
            else:
                rows = self._con.execute(
                    "SELECT body, hash FROM ledger WHERE order_id = ? ORDER BY seq", (order_id,)
                ).fetchall()
        return [_entry(b, h) for b, h in rows]

    def verify(self) -> VerifyResult:
        prev = GENESIS
        count = 0
        expected_seq = 1
        with self._lock:
            head = self.head()
            rows = self._con.execute("SELECT seq, order_id, body, hash FROM ledger ORDER BY seq").fetchall()
        for stored_seq, order_id, body_text, h in rows:
            try:
                body = json.loads(body_text)
            except ValueError:
                return VerifyResult(False, count, stored_seq)
            if (
                not isinstance(body, dict)
                or set(body) != set(FIELDS)
                or stored_seq != expected_seq
                or body.get("seq") != stored_seq
                or body.get("prev_hash") != prev
                or body.get("order_id") != order_id
                or entry_hash(body) != h
            ):
                return VerifyResult(False, count, stored_seq)
            prev = h
            count += 1
            expected_seq += 1
        if head is None:
            return VerifyResult(False, count, 1)
        if head.count != count or head.hash != prev:
            if count > head.count:  # entries past the head: the first one the head does not cover
                return VerifyResult(False, count, head.count + 1)
            # entries are missing at the end: the first missing seq, or the last one if the head itself changed
            return VerifyResult(False, count, min(count + 1, max(head.count, 1)))
        if self.public is not None and not head_signature_ok(head, self.public):
            # every row and the head agree, but the kitchen never signed this head: nothing in it can be trusted
            return VerifyResult(False, count, 1)
        return VerifyResult(True, count, None)


def _entry(body_text: str, h: str) -> AuditEntry:
    """An entry for display even when its row was tampered with; verify() says whether to trust it."""
    try:
        body = json.loads(body_text)
    except ValueError:
        body = None
    if not isinstance(body, dict):
        body = {"sentence": "(this entry is not readable)"}
    v = {k: body.get(k) for k in FIELDS}
    return AuditEntry(
        seq=v["seq"] if isinstance(v["seq"], int) else 0, at=str(v["at"] or ""), actor=str(v["actor"] or ""),
        kind=str(v["kind"] or ""), sentence=str(v["sentence"] or ""),
        facts=[f for f in v["facts"] if isinstance(f, dict)] if isinstance(v["facts"], list) else [],
        mandate_id=None if v["mandate_id"] is None else str(v["mandate_id"]),
        disclosed=v["disclosed"] if isinstance(v["disclosed"], dict) else {},
        rule_ids=[str(r) for r in v["rule_ids"]] if isinstance(v["rule_ids"], list) else [],
        order_id=None if v["order_id"] is None else str(v["order_id"]),
        prev_hash=str(v["prev_hash"] or ""), hash=h,
    )
