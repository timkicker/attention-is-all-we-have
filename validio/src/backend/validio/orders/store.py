"""Requests, orders and idempotency keys in the local SQLite store (data/validio.db, the same file the
demo seed writes). Each record is one JSON document, ids count up from a reset (R-1, O-1, ...)."""

import contextlib
import itertools
import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

SCHEMA = """
create table if not exists supply_request (id text primary key, n integer, body text not null);
create table if not exists supply_order (id text primary key, n integer, request_id text, body text not null);
create table if not exists idempotency (scope text, key text, body_hash text, ref text,
                                        primary key (scope, key));
create table if not exists seen_pass (id text primary key, body text not null);
create unique index if not exists one_order_per_request on supply_order(request_id) where request_id is not null;
create table if not exists revoked_pass (id text primary key, at text not null, by text not null);
"""


class NotFound(LookupError):
    """No request or order with this id (HTTP 404). A bare KeyError is a bug, never a 404."""


_SERIALS = itertools.count(1)


class Store:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.serial = next(_SERIALS)  # unique in the process for the store's life, never reused (unlike id())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # timeout: a second connection to the same file (an account's runtime dropped from the cache while a
        # request still uses it) waits for the other's write instead of failing at once
        self._con = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False, timeout=30)
        self._lock = threading.RLock()
        self._depth = 0
        self._con.executescript(SCHEMA)

    @property
    def lock(self) -> threading.RLock:
        """Held by every call on the connection; the ledger takes it too when it shares the connection."""
        return self._lock

    @property
    def con(self) -> sqlite3.Connection:
        """The one connection; the Open Ledger shares it, so an order and its entry commit together."""
        return self._con

    def close(self) -> None:
        self._con.close()

    def __del__(self) -> None:  # an account's runtime dropped from the cache closes when nothing holds it
        with contextlib.suppress(Exception):  # at interpreter shutdown the module may be half gone
            self._con.close()

    @contextmanager
    def tx(self) -> Iterator[None]:
        """One SQLite transaction for everything inside, nested calls join the outer one."""
        with self._lock:
            if self._depth:
                self._depth += 1
                try:
                    yield
                finally:
                    self._depth -= 1
                return
            self._con.execute("BEGIN IMMEDIATE")
            self._depth = 1
            try:
                yield
            except BaseException:
                self._con.execute("ROLLBACK")
                raise
            else:
                self._con.execute("COMMIT")
            finally:
                self._depth = 0

    def _next(self, table: str, prefix: str) -> tuple[str, int]:
        (n,) = self._con.execute(f"select coalesce(max(n), 0) + 1 from {table}").fetchone()
        return f"{prefix}-{n}", n

    def new_request(self, body: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            rid, n = self._next("supply_request", "R")
            body = {**body, "id": rid}
            self._con.execute("insert into supply_request values (?, ?, ?)", (rid, n, json.dumps(body)))
            return body

    def put_request(self, body: dict[str, Any]) -> None:
        with self._lock:
            self._con.execute("update supply_request set body = ? where id = ?", (json.dumps(body), body["id"]))

    def request(self, rid: str) -> dict[str, Any] | None:
        with self._lock:  # reads take the lock too: worker threads share this one connection
            row = self._con.execute("select body from supply_request where id = ?", (rid,)).fetchone()
        return json.loads(row[0]) if row else None

    def requests(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._con.execute("select body from supply_request order by n").fetchall()
        return [json.loads(b) for (b,) in rows]

    def new_order(self, body: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            oid, n = self._next("supply_order", "O")
            body = {**body, "id": oid}
            self._con.execute("insert into supply_order values (?, ?, ?, ?)",
                              (oid, n, body.get("requestId"), json.dumps(body)))
            return body

    def put_order(self, body: dict[str, Any]) -> None:
        with self._lock:
            self._con.execute("update supply_order set body = ? where id = ?", (json.dumps(body), body["id"]))

    def order(self, oid: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._con.execute("select body from supply_order where id = ?", (oid,)).fetchone()
        return json.loads(row[0]) if row else None

    def order_for_request(self, rid: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._con.execute("select body from supply_order where request_id = ?", (rid,)).fetchone()
        return json.loads(row[0]) if row else None

    def orders(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._con.execute("select body from supply_order order by n").fetchall()
        return [json.loads(b) for (b,) in rows]

    def idem_get(self, scope: str, key: str) -> tuple[str, str] | None:
        with self._lock:
            row = self._con.execute("select body_hash, ref from idempotency where scope = ? and key = ?",
                                    (scope, key)).fetchone()
        return (row[0], row[1]) if row else None

    def steady_orders(self) -> dict[str, str]:
        """Order id to the Steady Order that placed it, read from its idempotency key "steady:S-1:..."."""
        with self._lock:
            rows = self._con.execute("select key, ref from idempotency where key like 'steady:%'").fetchall()
        return {ref: key.split(":")[1] for key, ref in rows}

    def idem_put(self, scope: str, key: str, body_hash: str, ref: str) -> None:
        with self._lock:
            self._con.execute("insert into idempotency values (?, ?, ?, ?)", (scope, key, body_hash, ref))

    def idem_delete(self, scope: str, key: str) -> None:
        with self._lock:
            self._con.execute("delete from idempotency where scope = ? and key = ?", (scope, key))

    def drop_request(self, rid: str) -> None:
        """Forget a request that never got past its start (an error before any decision)."""
        with self._lock:
            self._con.execute("delete from supply_request where id = ?", (rid,))

    def remember_pass(self, pass_id: str, body: dict[str, Any]) -> None:
        with self._lock:
            self._con.execute("insert or replace into seen_pass values (?, ?)", (pass_id, json.dumps(body)))

    def revoke(self, pass_id: str, at: str, by: str) -> bool:
        """Put a Spend Pass on the kitchen's revocation list. False when it was on it already."""
        with self._lock:
            cur = self._con.execute("insert or ignore into revoked_pass values (?, ?, ?)", (pass_id, at, by))
            return cur.rowcount == 1

    def is_revoked(self, pass_id: str) -> bool:
        with self._lock:
            return self._con.execute("select 1 from revoked_pass where id = ?", (pass_id,)).fetchone() is not None

    def seen_pass(self, pass_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._con.execute("select body from seen_pass where id = ?", (pass_id,)).fetchone()
        return json.loads(row[0]) if row else None
