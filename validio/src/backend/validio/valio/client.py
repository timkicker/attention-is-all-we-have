"""Valio test API client: price and availability for a few candidates, with record and replay.

live    calls the test API
record  calls it and stores every answer under cache_dir
replay  answers only from cache_dir and never opens a connection
"""

import hashlib
import json
import time
from datetime import date
from pathlib import Path

import httpx

from .budget import CallBudget
from .models import Availability, Quote

MAX_PER_CALL = 1000  # Valio rejects longer lists with 422
TEST_API_HOST = "junction26.valioaimo.fi"  # Valio's test API. The real webshop is never called.


class ReplayMiss(LookupError):
    pass


class ValioUnavailable(RuntimeError):
    """Valio timed out, could not be reached or answered 5xx, twice. Nothing was ordered."""

    def __init__(self, cause: Exception | None = None):
        super().__init__("Valio did not answer. Nothing was ordered.")
        self.cause = cause


def _transient(e: Exception) -> bool:
    if isinstance(e, httpx.HTTPStatusError):
        return e.response.status_code >= 500
    return isinstance(e, httpx.TransportError)  # timeouts, refused or dropped connections


def checked_base_url(url: str) -> str:
    """The base URL when it is exactly https://junction26.valioaimo.fi, else ValueError. Parsed, not grepped,
    so letter case, a user name or a look-alike host cannot get the key to another server."""
    u = httpx.URL(url)
    if u.scheme != "https" or u.host.lower() != TEST_API_HOST or u.userinfo or u.port not in (None, 443):
        raise ValueError(f"refusing {u.host or url!r}: only https://{TEST_API_HOST} is allowed")
    return f"https://{TEST_API_HOST}"


def replay_key(endpoint: str, requested: date, ids: list[str]) -> str:
    return hashlib.sha256(f"{endpoint}|{requested.isoformat()}|{','.join(sorted(ids))}".encode()).hexdigest()


class ValioClient:
    def __init__(self, base_url: str, api_key: str, mode: str, cache_dir: Path | None,
                 customer: str = "hotel-espoo", chunk: int = MAX_PER_CALL, http: httpx.Client | None = None,
                 backoff: float = 0.5):
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
        self.backoff = backoff
        self._index: dict[tuple[str, str], tuple[dict, dict[str, dict], set[str]]] = {}

    def price(self, ids: list[str], requested: date, budget: CallBudget) -> dict[str, Quote]:
        out: dict[str, Quote] = {}
        for resp in self._query("price", ids, requested, budget):
            for x in resp["products"]:
                out[x["productId"]] = Quote.from_api(x)
        return out

    def availability(self, ids: list[str], requested: date, budget: CallBudget) -> dict[str, Availability]:
        out: dict[str, Availability] = {}
        for resp in self._query("availability", ids, requested, budget):
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

    def _call(self, endpoint: str, requested: date, ids: list[str]) -> dict:
        """One read, asked once more after a short pause when Valio times out, cannot be reached or answers 5xx.
        Both endpoints only read: Validio places orders in its own store, never at Valio, so a second try
        cannot order twice. Anything that would place an order must not come through here."""
        try:
            return self._call_once(endpoint, requested, ids)
        except httpx.HTTPError as e:
            if not _transient(e):
                raise
        time.sleep(self.backoff)
        try:
            return self._call_once(endpoint, requested, ids)
        except httpx.HTTPError as e:
            if not _transient(e):
                raise
            raise ValioUnavailable(e) from e

    def _call_once(self, endpoint: str, requested: date, ids: list[str]) -> dict:
        body = {"customer": self.customer, "requestedDate": requested.isoformat(), "products": ids}
        http = self._http or httpx.Client(timeout=30)
        try:
            req = http.build_request("POST", f"{self.base_url}/api/{endpoint}", json=body,
                                     headers={"X-API-Key": self._api_key})
            checked_base_url(str(req.url))  # every request, not only the base: an injected client cannot redirect it
            r = http.send(req, follow_redirects=False)  # never follow, whatever the client was built with
            r.raise_for_status()
            resp = r.json()
        finally:
            if self._http is None:
                http.close()
        if self.mode == "record":
            d = self.cache_dir / endpoint / requested.isoformat()
            d.mkdir(parents=True, exist_ok=True)
            (d / f"{replay_key(endpoint, requested, ids)}.json").write_text(json.dumps(
                {"endpoint": endpoint, "requestedDate": requested.isoformat(), "ids": sorted(ids),
                 "response": resp}, indent=1, ensure_ascii=False))
        return resp

    def _replay(self, endpoint: str, requested: date, ids: list[str]) -> dict:
        d = self.cache_dir / endpoint / requested.isoformat()
        exact = d / f"{replay_key(endpoint, requested, ids)}.json"
        if exact.is_file():
            return json.loads(exact.read_text())["response"]
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
            self._index[key] = (heads, rows, clash)
        heads, rows, clash = self._index[key]
        if bad := [i for i in ids if i in clash]:
            raise ReplayMiss(f"recordings disagree on {endpoint} for {bad} on {requested}, run make record")
        missing = [i for i in ids if i not in rows]
        if missing:
            raise ReplayMiss(f"no recorded {endpoint} answer for {missing} on {requested}, run make record first")
        # recordings made at different times carry different clocks: the earliest one asked counts, so a
        # later recording of other products never moves an earlier answer's timeNow
        head = min((heads[i] for i in ids), key=lambda h: json.dumps(h, sort_keys=True), default={})
        return {**head, "products": [rows[i] for i in ids]}
