"""Keeps a live check answering when Gemini is slow, failing or out of quota.

Each check gets a time budget for Gemini (CHECK_GEMINI_BUDGET_S, one call at most CHECK_GEMINI_CALL_S). A call that
fails or runs past either limit is replaced by the similarity guess, so the visitor always gets a result and every
statement says which of the two judged it. After BREAKER_FAILS failures within a minute, and after GEMINI_DAILY_CAP
calls in one UTC day, checks skip Gemini entirely (for BREAKER_PAUSE_S, or until the next day)."""

import datetime as dt
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout

BUDGET_S = float(os.environ.get("CHECK_GEMINI_BUDGET_S", "30"))
CALL_S = float(os.environ.get("CHECK_GEMINI_CALL_S", "15"))
BREAKER_FAILS = int(os.environ.get("GEMINI_BREAKER_FAILS", "5"))
BREAKER_PAUSE_S = float(os.environ.get("GEMINI_BREAKER_PAUSE_S", "300"))
DAILY_CAP = int(os.environ.get("GEMINI_DAILY_CAP", "5000"))

_LOCK = threading.Lock()
_fails: list[float] = []
_open_until = 0.0
_day = ""
_calls_today = 0
# calls run here so a stuck one can be abandoned; the thread finishes on its own and its answer is dropped
_POOL = ThreadPoolExecutor(max_workers=int(os.environ.get("GEMINI_GUARD_THREADS", "64")))


def _today() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%d")


def available() -> bool:
    with _LOCK:
        if _day == _today() and _calls_today >= DAILY_CAP:
            return False
        return time.monotonic() >= _open_until


def _count_call() -> None:
    global _day, _calls_today
    with _LOCK:
        if _day != _today():
            _day, _calls_today = _today(), 0
        _calls_today += 1


def _fail() -> None:
    global _open_until
    now = time.monotonic()
    with _LOCK:
        _fails[:] = [t for t in _fails if now - t < 60] + [now]
        if len(_fails) >= BREAKER_FAILS:
            _open_until = now + BREAKER_PAUSE_S
            _fails.clear()


def status() -> dict:
    with _LOCK:
        return {
            "open": time.monotonic() >= _open_until,
            "calls_today": _calls_today if _day == _today() else 0,
            "daily_cap": DAILY_CAP,
        }


class Budget:
    """One check's deadline."""

    def __init__(self, seconds: float = BUDGET_S) -> None:
        self.deadline = time.monotonic() + seconds

    def left(self) -> float:
        return self.deadline - time.monotonic()

    def call(self, fn, *args):
        """fn(*args) or None when Gemini is off, the budget is spent, the call fails or it takes too long."""
        wait = min(CALL_S, self.left())
        if wait <= 0 or not available():
            return None
        _count_call()
        fut = _POOL.submit(fn, *args)
        try:
            return fut.result(timeout=wait)
        except FutureTimeout:
            _fail()
            return None
        except Exception:  # noqa: BLE001  (any model failure falls back to the guess)
            _fail()
            return None


def reset() -> None:
    """Tests only."""
    global _open_until, _day, _calls_today
    with _LOCK:
        _fails.clear()
        _open_until, _day, _calls_today = 0.0, "", 0
