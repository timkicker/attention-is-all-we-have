"""Requests, orders and idempotency keys in the local SQLite store (data/validio.db, the same file the
demo seed writes). Each record is one JSON document, ids count up from a reset (R-1, O-1, ...)."""

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

SCHEMA = """
create table if not exists supply_request (id text primary key, n integer, body text not null);
create table if not exists supply_order (id text primary key, n integer, request_id text, body text not null);
create table if not exists idempotency (scope text, key text, body_hash text, ref text,
                                        primary key (scope, key));
create table if not exists seen_pass (id text primary key, body text not null);
"""


class Store:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False)
        self._lock = threading.RLock()
        self._con.executescript(SCHEMA)

    def close(self) -> None:
        self._con.close()

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
        row = self._con.execute("select body from supply_request where id = ?", (rid,)).fetchone()
        return json.loads(row[0]) if row else None

    def requests(self) -> list[dict[str, Any]]:
        return [json.loads(b) for (b,) in self._con.execute("select body from supply_request order by n")]

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
        row = self._con.execute("select body from supply_order where id = ?", (oid,)).fetchone()
        return json.loads(row[0]) if row else None

    def orders(self) -> list[dict[str, Any]]:
        return [json.loads(b) for (b,) in self._con.execute("select body from supply_order order by n")]

    def idem_get(self, scope: str, key: str) -> tuple[str, str] | None:
        row = self._con.execute("select body_hash, ref from idempotency where scope = ? and key = ?",
                                (scope, key)).fetchone()
        return (row[0], row[1]) if row else None

    def idem_put(self, scope: str, key: str, body_hash: str, ref: str) -> None:
        with self._lock:
            self._con.execute("insert into idempotency values (?, ?, ?, ?)", (scope, key, body_hash, ref))

    def remember_pass(self, pass_id: str, body: dict[str, Any]) -> None:
        with self._lock:
            self._con.execute("insert or replace into seen_pass values (?, ?)", (pass_id, json.dumps(body)))

    def seen_pass(self, pass_id: str) -> dict[str, Any] | None:
        row = self._con.execute("select body from seen_pass where id = ?", (pass_id,)).fetchone()
        return json.loads(row[0]) if row else None
