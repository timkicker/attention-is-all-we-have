"""Gemini through its OpenAI-compatible endpoint (PLAN A9), shared by judge, splitter and gloss.

One key for the whole team means one quota: a token bucket of RPM requests per minute, at most 4 in flight,
backoff on 429 and 5xx (Retry-After, else 2 s doubling to 60 s, 5 attempts), one extra try on unparseable JSON.
The key is read from the environment and never logged.
"""

import json
import os
import re
import threading
import time

from contract.db import load_env

BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
MODEL = "gemini-3.8-flash"
RPM = 60
MAX_IN_FLIGHT = 4
MAX_ATTEMPTS = 5
TIMEOUT = 60
STATS = {"calls": 0, "r429": 0, "retries": 0, "bad_json": 0, "failed": 0, "seconds": 0.0}
_LOCK = threading.Lock()


class GeminiError(RuntimeError):
    pass


class TokenBucket:
    def __init__(self, rpm: int, clock=time.monotonic, sleep=time.sleep) -> None:
        self.rate = rpm / 60.0
        self.capacity = max(1.0, rpm / 10)
        self.tokens = self.capacity
        self.clock, self.sleep = clock, sleep
        self.last = clock()
        self.lock = threading.Lock()

    def take(self) -> None:
        while True:
            with self.lock:
                now = self.clock()
                self.tokens = min(self.capacity, self.tokens + (now - self.last) * self.rate)
                self.last = now
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
                wait = (1 - self.tokens) / self.rate
            self.sleep(wait)


_BUCKET = TokenBucket(RPM)
_SEM = threading.BoundedSemaphore(MAX_IN_FLIGHT)
_CLIENT = None


def client():
    global _CLIENT
    if _CLIENT is None:
        load_env()
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise GeminiError("GEMINI_API_KEY is not set in parallax/.env")
        from openai import OpenAI

        _CLIENT = OpenAI(api_key=key, base_url=BASE_URL, timeout=TIMEOUT, max_retries=0)
    return _CLIENT


def parse_json(text: str):
    """JSON from a model answer, tolerating code fences or prose around one object or list."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        return json.loads(text)
    except ValueError:
        pass
    for open_, close in (("{", "}"), ("[", "]")):
        a, b = text.find(open_), text.rfind(close)
        if a != -1 and b > a:
            try:
                return json.loads(text[a : b + 1])
            except ValueError:
                continue
    raise ValueError("no JSON in answer")


def _status(exc) -> int | None:
    return getattr(exc, "status_code", None) or getattr(getattr(exc, "response", None), "status_code", None)


def _retry_after(exc) -> float | None:
    resp = getattr(exc, "response", None)
    ra = resp.headers.get("retry-after") if resp is not None and hasattr(resp, "headers") else None
    try:
        return float(ra) if ra else None
    except ValueError:
        return None


def ask_json(system: str, user: str, *, sleep=time.sleep, call=None) -> tuple[object, str]:
    """(parsed JSON, raw text). `call(messages)` replaces the API call in tests."""
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    effort = os.environ.get("GEMINI_REASONING_EFFORT", "low")  # the endpoint answers 400 to "minimal"

    def api(msgs):
        kw = {"model": MODEL, "messages": msgs, "temperature": 0, "response_format": {"type": "json_object"}}
        if effort:
            kw["reasoning_effort"] = effort
        r = client().chat.completions.create(**kw)
        return r.choices[0].message.content or ""

    call = call or api
    wait = 2.0
    bad_json_left = 1
    for attempt in range(1, MAX_ATTEMPTS + 1):
        _BUCKET.take()
        t = time.time()
        try:
            with _SEM:
                with _LOCK:
                    STATS["calls"] += 1
                raw = call(messages)
        except Exception as e:  # noqa: BLE001  (the SDK raises several types; status decides)
            status = _status(e)
            if status == 429 or (status and status >= 500) or status is None and "timeout" in str(e).lower():
                with _LOCK:
                    STATS["r429" if status == 429 else "retries"] += 1
                if attempt == MAX_ATTEMPTS:
                    break
                sleep(_retry_after(e) or wait)
                wait = min(60.0, wait * 2)
                continue
            with _LOCK:
                STATS["failed"] += 1
            raise GeminiError(f"Gemini call failed with status {status}") from None
        finally:
            with _LOCK:
                STATS["seconds"] += time.time() - t
        try:
            return parse_json(raw), raw
        except ValueError:
            with _LOCK:
                STATS["bad_json"] += 1
            if bad_json_left:
                bad_json_left -= 1
                continue
            raise GeminiError("answer was not JSON twice") from None
    with _LOCK:
        STATS["failed"] += 1
    raise GeminiError("Gemini gave up after retries")


def stats_line() -> str:
    return " ".join(f"{k}={round(v, 1) if isinstance(v, float) else v}" for k, v in STATS.items())
