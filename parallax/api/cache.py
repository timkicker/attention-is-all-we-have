"""A small in-process cache for read-only GET responses, keyed by path and full query string.

The data only changes through ingest and POST /api/check, so the cache is cleared after every successful
write request and whenever the ingest worker finishes a job; TTL_S bounds anything else (an ingest that makes
a topic usable while it still runs). Concurrent misses on one key wait for the first one (single flight),
so fifty visitors opening the same page cost the database one query set, not fifty.
"""

import asyncio
import gzip
import hashlib
import threading
import time
from collections import OrderedDict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from urllib.parse import parse_qs

from starlette.requests import Request

# An ingest clears the cache whenever it stores an edition and when it finishes, so the TTL only bounds what
# nothing clears; a cold Differences page is seconds of vector search, so entries are kept for a while.
TTL_S = 900.0
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
    gz: bytes = b""  # body compressed once, served as is to clients that accept gzip (Caddy passes it through)
    etag: str = ""


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


def put(k: str, gen: int, body: bytes, headers: dict[str, str], panel: str | None, statements: list[dict]) -> Entry:
    """Store a response computed while generation `gen` was current; not stored if a clear() came in between."""
    entry = make_entry(gen, body, headers, panel, statements)
    with _mutex:
        if gen != _gen:
            return entry
        _store[k] = entry
        _store.move_to_end(k)
        while len(_store) > MAX_ENTRIES:
            _store.popitem(last=False)
    return entry


def make_entry(gen: int, body: bytes, headers: dict[str, str], panel: str | None, statements: list[dict]) -> Entry:
    etag = '"' + hashlib.blake2b(body, digest_size=12).hexdigest() + '"'
    gz = gzip.compress(body, compresslevel=6, mtime=0)
    return Entry(time.monotonic(), gen, body, headers, panel, statements, gz, etag)


def _topic(k: str) -> str | None:
    found = parse_qs(k.partition("?")[2]).get("topic")
    return found[0].lower() if found else None


def clear(topic: str | None = None) -> None:
    """Drop every cached answer. With a topic (an ingest stored data of that topic only) the answers of the other
    topics stay, so loading one article does not make every other article slow again; answers without a topic
    (lists, stats, search, statement histories) go either way."""
    global _gen
    with _mutex:
        _gen += 1
        if topic is None:
            _store.clear()
            return
        for k, e in list(_store.items()):
            other = _topic(k)
            if other is not None and other != topic.lower():
                _store[k] = replace(e, gen=_gen)
            else:
                del _store[k]


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
