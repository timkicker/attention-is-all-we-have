"""Times every statement of a request and keeps the last statements per panel for "Under the hood".

Routes run SQL only through run() or run_file(). The middleware in main.py opens a capture per request,
adds the captured list as `sql` to the JSON body and stores it under the panel the route named.
"""

import contextvars
import re
import time
from collections.abc import Iterator
from contextlib import contextmanager
from functools import cache
from pathlib import Path

from api.db import connection

QUERIES = Path(__file__).resolve().parent / "queries"
_current: contextvars.ContextVar[dict | None] = contextvars.ContextVar("sqllog", default=None)
LAST: dict[str, list[dict]] = {}  # panel_id -> statements of its last run


@cache
def query(name: str) -> str:
    """The text of api/queries/<name>.sql without leading comment lines."""
    lines = (QUERIES / f"{name}.sql").read_text(encoding="utf-8").splitlines()
    return "\n".join(line for line in lines if not line.lstrip().startswith("--")).strip().rstrip(";")


@contextmanager
def capture() -> Iterator[list[dict]]:
    state = {"statements": [], "panel": None}
    token = _current.set(state)
    try:
        yield state["statements"]
    finally:
        _current.reset(token)


def panel(panel_id: str) -> None:
    """Name the panel whose statements this request records."""
    state = _current.get()
    if state is not None:
        state["panel"] = panel_id


def current_panel() -> str | None:
    state = _current.get()
    return state["panel"] if state else None


_VEC = re.compile(r"VEC_DISTANCE", re.I)


def _index_used(cur, text: str, params) -> str:
    if not _VEC.search(text):
        return "none"
    try:
        cur.execute("EXPLAIN " + text, params)
        cols = [d[0] for d in cur.description]
        keys = [dict(zip(cols, row, strict=False)).get("key") for row in cur.fetchall()]
        return "emb" if "emb" in keys else "none"
    except Exception:
        return "none"


def run(text: str, params=None) -> list[dict]:
    """Execute one statement, log {text, ms, rows, index} and return the rows as dicts."""
    with connection() as conn, conn.cursor() as cur:
        t0 = time.perf_counter()
        cur.execute(text, params)
        rows = cur.fetchall()
        ms = (time.perf_counter() - t0) * 1000
        cols = [d[0] for d in cur.description] if cur.description else []
        out = [dict(zip(cols, r, strict=False)) for r in rows]
        index = _index_used(cur, text, params)
    state = _current.get()
    if state is not None:
        state["statements"].append({"text": text, "ms": round(ms, 2), "rows": len(out), "index": index})
    return out


def run_file(name: str, params=None) -> list[dict]:
    return run(query(name), params)
