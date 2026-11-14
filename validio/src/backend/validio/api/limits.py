"""Rate limits for the routes anyone can reach, and the client address they count by.

In memory, per process: Modal runs one container (src/cloud/app_validio.py), so one process sees every call.
The address is the TCP peer, or with VALIDIO_TRUST_PROXY=1 the left-most X-Forwarded-For entry, for a deploy
behind a proxy that sets it. Never trust that header without the switch: a caller could name any address."""

import os
import threading
import time
from collections import deque
from collections.abc import Callable

from fastapi import HTTPException, Request


def client_ip(request: Request) -> str:
    if os.environ.get("VALIDIO_TRUST_PROXY") == "1":
        fwd = request.headers.get("x-forwarded-for", "")
        first = fwd.split(",", 1)[0].strip()
        if first:
            return first
    return request.client.host if request.client else "?"


class RateLimiter:
    """At most `limit` hits per key within `window` seconds (a sliding window)."""

    def __init__(self, limit: int, window: float, clock: Callable[[], float] = time.monotonic,
                 max_keys: int = 50_000):
        self.limit, self.window, self.clock, self.max_keys = limit, window, clock, max_keys
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def _recent(self, key: str, now: float) -> deque[float]:
        q = self._hits.get(key)
        if q is None:
            if len(self._hits) >= self.max_keys:  # never grows without bound
                self._hits.pop(next(iter(self._hits)))
            q = self._hits[key] = deque()
        while q and q[0] <= now - self.window:
            q.popleft()
        return q

    def blocked(self, key: str) -> bool:
        with self._lock:
            return len(self._recent(key, self.clock())) >= self.limit

    def hit(self, key: str) -> None:
        with self._lock:
            now = self.clock()
            self._recent(key, now).append(now)

    def check(self, key: str, what: str = "requests") -> None:
        """Count one hit, 429 once the key used up its window."""
        with self._lock:
            now = self.clock()
            q = self._recent(key, now)
            if len(q) >= self.limit:
                raise HTTPException(429, f"too many {what}, try again in a minute",
                                    headers={"Retry-After": str(int(self.window))})
            q.append(now)

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()


# a nonce is fetched once per agent call: 120 a minute per client and kitchen is far above any real agent
NONCES = RateLimiter(120, 60)
# the MCP nonce resources cannot see the caller's address: a cap per kitchen
MCP_NONCES = RateLimiter(600, 60)
# a signup or a demo copy writes a whole kitchen (db and keys): 10 an hour per client
NEW_KITCHENS = RateLimiter(10, 3600)
