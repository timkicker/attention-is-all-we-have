"""A small in-process cache for read-only GET responses, keyed by path and full query string.

The data only changes through ingest and POST /api/check, so the cache is cleared after every successful
write request and whenever the ingest worker finishes a job; TTL_S bounds anything else (an ingest that makes
a topic usable while it still runs). Concurrent misses on one key wait for the first one (single flight),
so fifty visitors opening the same page cost the database one query set, not fifty.
"""

import asyncio
import threading
import time
from collections import OrderedDict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from starlette.requests import Request

TTL_S = 60.0
MAX_ENTRIES = 512
# Never cached: progress that changes by the second, the SQL panels (they show the last run) and the health probe.
SKIP_PREFIXES = ("/api/ingest", "/api/sql/", "/api/health")


@dataclass(frozen=True)
class Entry:
    at: float
    gen: int
    body: bytes
    headers: dict[str, str]
    panel: str | None
    statements: list[dict]


_store: "OrderedDict[str, Entry]" = OrderedDict()
_locks: dict[str, tuple[asyncio.Lock, int]] = {}
_mutex = threading.Lock()  # clear() runs on the ingest worker thread
_gen = 0


def key(request: Request) -> str | None:
    """The cache key of a request, None when it must not be cached."""
    path = request.url.path
    if request.method != "GET" or not path.startswith("/api/") or path.startswith(SKIP_PREFIXES):
        return None
    return f"{path}?{request.url.query}"


def generation() -> int:
    return _gen


def get(k: str) -> Entry | None:
    with _mutex:
        e = _store.get(k)
        if e is None:
            return None
        if e.gen != _gen or time.monotonic() - e.at > TTL_S:
            del _store[k]
            return None
        _store.move_to_end(k)
        return e


def put(k: str, gen: int, body: bytes, headers: dict[str, str], panel: str | None, statements: list[dict]) -> None:
    """Store a response computed while generation `gen` was current; dropped if a clear() came in between."""
    with _mutex:
        if gen != _gen:
            return
        _store[k] = Entry(time.monotonic(), gen, body, headers, panel, statements)
        _store.move_to_end(k)
        while len(_store) > MAX_ENTRIES:
            _store.popitem(last=False)


def clear() -> None:
    global _gen
    with _mutex:
        _gen += 1
        _store.clear()


@asynccontextmanager
async def single_flight(k: str) -> AsyncIterator[None]:
    """Hold the per-key lock: the first miss computes, the others wait and then find its entry."""
    lock, users = _locks.get(k, (asyncio.Lock(), 0))
    _locks[k] = (lock, users + 1)
    try:
        async with lock:
            yield
    finally:
        lock, users = _locks[k]
        if users == 1:
            del _locks[k]
        else:
            _locks[k] = (lock, users - 1)
