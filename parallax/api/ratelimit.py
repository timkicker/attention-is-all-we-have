"""Per-visitor limits for the routes that cost model calls, Wikipedia requests or ingest work.

One process serves the demo, so the buckets live in memory. A visitor is the client address uvicorn reports; behind
Caddy that is the X-Forwarded-For address once uvicorn runs with --proxy-headers (deploy/Dockerfile). Each limit is
a token bucket: `burst` requests at once, refilled at `per_minute`. Limits can be tuned with RATE_<NAME> =
"<per_minute>/<burst>" in the environment; RATE_LIMITS=0 turns them off (tests, local runs).
"""

import math
import os
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass

from fastapi import Request

from api.util import ApiError

MAX_KEYS = 10_000  # visitors remembered per limit; the least recently seen are forgotten first

DEFAULTS = {
    "check": (2.0, 5),  # each check splits and judges an answer with the model
    "ingest": (0.2, 3),  # each new article is minutes of embedding and dozens of model calls
    "search": (60.0, 20),  # each search asks Wikipedia up to five times
    "ask": (20.0, 10),  # each question is embedded
}


@dataclass
class _Bucket:
    tokens: float
    at: float


class Limit:
    def __init__(self, name: str, per_minute: float, burst: int, clock=time.monotonic) -> None:
        self.name = name
        self.rate = per_minute / 60.0
        self.burst = burst
        self.clock = clock
        self._buckets: OrderedDict[str, _Bucket] = OrderedDict()
        self._lock = threading.Lock()

    def take(self, key: str) -> float:
        """0 when the request may go ahead, else the seconds until it may."""
        now = self.clock()
        with self._lock:
            b = self._buckets.pop(key, None) or _Bucket(float(self.burst), now)
            b.tokens = min(self.burst, b.tokens + (now - b.at) * self.rate)
            b.at = now
            self._buckets[key] = b
            while len(self._buckets) > MAX_KEYS:
                self._buckets.popitem(last=False)
            if b.tokens >= 1:
                b.tokens -= 1
                return 0.0
            return (1 - b.tokens) / self.rate if self.rate else 3600.0


def _config(name: str) -> tuple[float, int]:
    raw = os.environ.get(f"RATE_{name.upper()}")
    if raw:
        per_minute, _, burst = raw.partition("/")
        return float(per_minute), int(burst or 1)
    return DEFAULTS[name]


_LIMITS: dict[str, Limit] = {}
_LIMITS_LOCK = threading.Lock()


def _limit(name: str) -> Limit:
    with _LIMITS_LOCK:
        if name not in _LIMITS:
            _LIMITS[name] = Limit(name, *_config(name))
        return _LIMITS[name]


def enabled() -> bool:
    return os.environ.get("RATE_LIMITS", "1") != "0"


def too_many(seconds: float, message: str = "Too many requests. Try again later.") -> ApiError:
    s = max(1, math.ceil(seconds))
    err = ApiError(429, "too_many", message)  # Parallax's own limit; "rate_limited" means Wikipedia asked to wait
    err.detail["retry_after_s"] = s
    err.headers = {"Retry-After": str(s)}
    return err


def check(request: Request, name: str) -> None:
    """Raise 429 too_many when this visitor used up the `name` limit."""
    if not enabled():
        return
    visitor = request.client.host if request.client else "unknown"
    wait = _limit(name).take(visitor)
    if wait > 0:
        raise too_many(wait)


def reset() -> None:
    """Forget every bucket (tests)."""
    with _LIMITS_LOCK:
        _LIMITS.clear()
