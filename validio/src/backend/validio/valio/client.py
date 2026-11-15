"""Valio test API client: price and availability for a few candidates, with record and replay.

live    calls the test API
record  calls it and stores every answer under cache_dir
replay  answers only from cache_dir and never opens a connection, unless live_fallback is on
        (VALIO_LIVE_FALLBACK=1) and there is a key: then the ids or the day without a recording are asked from
        the test API, stored like record mode does, and replayed from then on
"""

import hashlib
import json
import logging
import threading
import time
from contextlib import contextmanager
from datetime import date
from pathlib import Path

import httpx

from .budget import CallBudget
from .models import Availability, Quote

MAX_PER_CALL = 1000  # Valio rejects longer lists with 422
TIMEOUT_S = 15.0  # one read; asked twice at most, so a request waits at most about 30 s on Valio
TEST_API_HOST = "junction26.valioaimo.fi"  # Valio's test API. The real webshop is never called.


class ReplayMiss(LookupError):
    pass


class NotRecorded(ReplayMiss):
    """A replay miss said for a person: what has no recording, never ids or make targets (those go to the log)."""


class ValioUnavailable(RuntimeError):
    """Valio timed out, could not be reached or answered 5xx, twice. Nothing was ordered."""

    reason_code = "valio_down"
    message = "Valio did not answer. Nothing was ordered."

    def __init__(self, cause: Exception | None = None):
        super().__init__(self.message)
        self.cause = cause


class ValioBusy(ValioUnavailable):
    """Valio answered 429: too many calls just now. Nothing was ordered; a minute later a retry may work."""

    message = "Valio is busy. Nothing was ordered. Try again in a minute."


class ValioRefused(ValioUnavailable):
    """Valio answered 401 or 403: it refused Validio's key. Nothing was ordered; asking again will not help
    until the key is fixed."""

    message = "Valio refused Validio's key. Nothing was ordered."


class ValioMalformed(ValioUnavailable):
    """Valio answered, but not in the shape Validio reads: a missing field, a bad number or time. Nothing was
    ordered; refused like an outage, never a 500 and never a guess."""

    message = "Valio answered in a shape Validio cannot read. Nothing was ordered."


def _refusal(e: Exception) -> ValioUnavailable | None:
    """429, 401 and 403 as Valio not answering, never a raw error (they used to become a 500)."""
    if isinstance(e, httpx.HTTPStatusError):
        code = e.response.status_code
        if code == 429:
            return ValioBusy(e)
        if code in (401, 403):
            return ValioRefused(e)
    return None


def _transient(e: Exception) -> bool:
    if isinstance(e, httpx.HTTPStatusError):
        return e.response.status_code >= 500
    return isinstance(e, httpx.TransportError)  # timeouts, refused or dropped connections


@contextmanager
def _readable(endpoint: str):
    """An answer Validio cannot read becomes ValioMalformed, with the cause in the log for the developer."""
    try:
        yield
    except (KeyError, TypeError, ValueError, AttributeError) as e:
        logging.getLogger(__name__).warning("unreadable Valio %s answer: %r", endpoint, e)
        raise ValioMalformed(e) from e


def checked_base_url(url: str) -> str:
    """The base URL when it is exactly https://junction26.valioaimo.fi, else ValueError. Parsed, not grepped,
    so letter case, a user name or a look-alike host cannot get the key to another server."""
    u = httpx.URL(url)
    if u.scheme != "https" or u.host.lower() != TEST_API_HOST or u.userinfo or u.port not in (None, 443):
        raise ValueError(f"refusing {u.host or url!r}: only https://{TEST_API_HOST} is allowed")
    return f"https://{TEST_API_HOST}"


def recorded_days(cache_dir: Path | None) -> list[date]:
    """The delivery days replay can answer: a folder with recordings under both price and availability."""
    if cache_dir is None:
        return []
    days = []
    for d in sorted(Path(cache_dir).glob("price/*")):
        try:
            day = date.fromisoformat(d.name)
        except ValueError:
            continue
        if any(d.glob("*.json")) and any((Path(cache_dir) / "availability" / d.name).glob("*.json")):
            days.append(day)
    return days


def days_text(days: list[date]) -> str:
    """"Mon 2026-11-16, Tue 2026-11-17": the weekday for a person, the ISO date for deliverBy."""
    return ", ".join(f"{d:%a} {d.isoformat()}" for d in days)


def replay_key(endpoint: str, requested: date, ids: list[str]) -> str:
    return hashlib.sha256(f"{endpoint}|{requested.isoformat()}|{','.join(sorted(ids))}".encode()).hexdigest()


class ValioClient:
    def __init__(self, base_url: str, api_key: str, mode: str, cache_dir: Path | None,
                 customer: str = "hotel-espoo", chunk: int = MAX_PER_CALL, http: httpx.Client | None = None,
                 backoff: float = 0.5, live_fallback: bool = False):
        base_url = checked_base_url(base_url)
        if mode not in ("live", "record", "replay"):
            raise ValueError(f"unknown mode {mode!r}")
        if mode != "live" and cache_dir is None:
            raise ValueError(f"mode {mode} needs a cache_dir")
        self.base_url, self.mode, self.customer = base_url, mode, customer
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.chunk = min(chunk, MAX_PER_CALL)
        self._api_key = api_key
        self._http = http
        self._pool: httpx.Client | None = None  # one client for every call: kept-alive TLS connections
        self._pool_lock = threading.Lock()
        self.backoff = backoff
        self.live_fallback = live_fallback
        self._index: dict[tuple[str, str], tuple[dict, dict[str, dict], set[str]]] = {}
        self._fallback_lock = threading.Lock()  # one live fallback at a time, so an id is never stored twice

    @property
    def falls_back(self) -> bool:
        """Replay that asks the test API for what has no recording: only with the switch on and a key."""
        return self.mode == "replay" and self.live_fallback and bool(self._api_key)

    def recorded_days(self) -> list[date] | None:
        """The days replay has answers for; None when the client asks Valio itself (any day)."""
        return recorded_days(self.cache_dir) if self.mode == "replay" and not self.falls_back else None

    def price(self, ids: list[str], requested: date, budget: CallBudget) -> dict[str, Quote]:
        out: dict[str, Quote] = {}
        for resp in self._query("price", ids, requested, budget):
            with _readable("price"):
                for x in resp["products"]:
                    out[x["productId"]] = Quote.from_api(x)
        return out

    def availability(self, ids: list[str], requested: date, budget: CallBudget) -> dict[str, Availability]:
        out: dict[str, Availability] = {}
        for resp in self._query("availability", ids, requested, budget):
            with _readable("availability"):
                for x in resp["products"]:
                    out[x["productId"]] = Availability.from_api(x, resp.get("timeNow"))
        return out

    def _query(self, endpoint: str, ids: list[str], requested: date, budget: CallBudget) -> list[dict]:
        ids = list(dict.fromkeys(ids))
        budget.reserve(ids)
        out = []
        for i in range(0, len(ids), self.chunk):
            part = ids[i:i + self.chunk]
            resp = self._replay(endpoint, requested, part) if self.mode == "replay" else \
                self._call(endpoint, requested, part)
            budget.count_call(len(part))
            out.append(resp)
        return out

    def _call(self, endpoint: str, requested: date, ids: list[str], store: bool = False) -> dict:
        """One read, asked once more after a short pause when Valio times out, cannot be reached or answers 5xx.
        Both endpoints only read: Validio places orders in its own store, never at Valio, so a second try
        cannot order twice. Anything that would place an order must not come through here. `store` keeps the
        answer under cache_dir as record mode does (the live fallback of replay)."""
        try:
            return self._call_once(endpoint, requested, ids, store)
        except httpx.HTTPError as e:
            if (r := _refusal(e)) is not None:
                raise r from e
            if not _transient(e):
                raise
        time.sleep(self.backoff)
        try:
            return self._call_once(endpoint, requested, ids, store)
        except httpx.HTTPError as e:
            if (r := _refusal(e)) is not None:
                raise r from e
            if not _transient(e):
                raise
            raise ValioUnavailable(e) from e

    def _call_once(self, endpoint: str, requested: date, ids: list[str], store: bool = False) -> dict:
        body = {"customer": self.customer, "requestedDate": requested.isoformat(), "products": ids}
        http = self._http or self._client()
        req = http.build_request("POST", f"{self.base_url}/api/{endpoint}", json=body,
                                 headers={"X-API-Key": self._api_key})
        checked_base_url(str(req.url))  # every request, not only the base: an injected client cannot redirect it
        r = http.send(req, follow_redirects=False)  # never follow, whatever the client was built with
        r.raise_for_status()
        with _readable(endpoint):
            resp = r.json()
            if not isinstance(resp, dict) or not isinstance(resp.get("products"), list):
                raise TypeError("no product list")
        if self.mode == "record" or store:
            d = self.cache_dir / endpoint / requested.isoformat()
            d.mkdir(parents=True, exist_ok=True)
            (d / f"{replay_key(endpoint, requested, ids)}.json").write_text(json.dumps(
                {"endpoint": endpoint, "requestedDate": requested.isoformat(), "ids": sorted(ids),
                 "response": resp}, indent=1, ensure_ascii=False))
        return resp

    def _client(self) -> httpx.Client:
        """The pooled client, made on first use; httpx.Client is safe to share between threads."""
        with self._pool_lock:
            if self._pool is None:
                self._pool = httpx.Client(timeout=httpx.Timeout(TIMEOUT_S, connect=5.0),
                                          limits=httpx.Limits(max_connections=20, max_keepalive_connections=10))
            return self._pool

    def _replay(self, endpoint: str, requested: date, ids: list[str]) -> dict:
        exact = self.cache_dir / endpoint / requested.isoformat() / f"{replay_key(endpoint, requested, ids)}.json"
        if exact.is_file():
            return json.loads(exact.read_text())["response"]
        heads, rows, missing = self._recorded(endpoint, requested, ids)
        if missing:
            if not self.falls_back:
                raise self._miss(endpoint, requested, missing)
            with self._fallback_lock:  # another request may have asked for the same ids meanwhile
                heads, rows, missing = self._recorded(endpoint, requested, ids)
                if missing:
                    self._fall_back(endpoint, requested, missing)
                    heads, rows, missing = self._recorded(endpoint, requested, ids)
            if missing:  # Valio's answer left some out: never a guess
                raise ValioMalformed(LookupError(f"no {endpoint} answer for {missing}"))
        # recordings made at different times carry different clocks: the earliest one asked counts, so a
        # later recording of other products never moves an earlier answer's timeNow
        head = min((heads[i] for i in ids), key=lambda h: json.dumps(h, sort_keys=True), default={})
        return {**head, "products": [rows[i] for i in ids]}

    def _recorded(self, endpoint: str, requested: date, ids: list[str]) -> tuple[dict, dict[str, dict], list[str]]:
        """The recorded heads and rows for that day, and the ids among `ids` without a recording."""
        d = self.cache_dir / endpoint / requested.isoformat()
        key = (endpoint, requested.isoformat())
        if key not in self._index:
            heads, rows, clash = {}, {}, set()
            for f in sorted(d.glob("*.json")):
                resp = json.loads(f.read_text())["response"]
                head = {k: v for k, v in resp.items() if k != "products"}
                for x in resp["products"]:
                    if rows.setdefault(x["productId"], x) != x:
                        clash.add(x["productId"])
                    heads.setdefault(x["productId"], head)
            if not rows:  # nothing for that day yet: asked again next time, a recording may come meanwhile
                return {}, {}, list(ids)
            self._index[key] = (heads, rows, clash)
        heads, rows, clash = self._index[key]
        if bad := [i for i in ids if i in clash]:
            raise ReplayMiss(f"recordings disagree on {endpoint} for {bad} on {requested}, run make record")
        return heads, rows, [i for i in ids if i not in rows]

    def _miss(self, endpoint: str, requested: date, missing: list[str]) -> ReplayMiss:
        if not any((self.cache_dir / endpoint / requested.isoformat()).glob("*.json")):
            days = days_text(recorded_days(self.cache_dir)) or "none"
            return ReplayMiss(f"no recorded {endpoint} answers for delivery on {requested}, recorded delivery days: "
                              f"{days}, run make record first")
        return ReplayMiss(f"no recorded {endpoint} answer for {missing} on {requested}, run make record first")

    def _fall_back(self, endpoint: str, requested: date, missing: list[str]) -> None:
        """Ask the test API for the ids without a recording only, and store the answer the way record mode does,
        so the next request replays it. Valio not answering is ValioUnavailable, as in live mode."""
        logging.getLogger(__name__).info("live fallback: %s for %d ids on %s", endpoint, len(missing), requested)
        self._call(endpoint, requested, missing, store=True)
        self._index.pop((endpoint, requested.isoformat()), None)  # read the folder again, with the new file
