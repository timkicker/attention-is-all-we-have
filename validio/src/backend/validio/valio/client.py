"""Valio test API client: price and availability for a few candidates, with record and replay.

live    calls the test API
record  calls it and stores every answer under cache_dir
replay  answers only from cache_dir and never opens a connection
"""

import hashlib
import json
from datetime import date
from pathlib import Path

import httpx

from .budget import CallBudget
from .models import Availability, Quote

MAX_PER_CALL = 1000  # Valio rejects longer lists with 422
FORBIDDEN = ("toimitustukku.valioaimo", "//api.valioaimo")  # Valio's real webshop, never


class ReplayMiss(LookupError):
    pass


def replay_key(endpoint: str, requested: date, ids: list[str]) -> str:
    return hashlib.sha256(f"{endpoint}|{requested.isoformat()}|{','.join(sorted(ids))}".encode()).hexdigest()


class ValioClient:
    def __init__(self, base_url: str, api_key: str, mode: str, cache_dir: Path | None,
                 customer: str = "hotel-espoo", chunk: int = MAX_PER_CALL, http: httpx.Client | None = None):
        if any(f in base_url for f in FORBIDDEN):
            raise ValueError("refusing Valio's real webshop, only the test API is allowed")
        if mode not in ("live", "record", "replay"):
            raise ValueError(f"unknown mode {mode!r}")
        if mode != "live" and cache_dir is None:
            raise ValueError(f"mode {mode} needs a cache_dir")
        self.base_url, self.mode, self.customer = base_url.rstrip("/"), mode, customer
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.chunk = min(chunk, MAX_PER_CALL)
        self._api_key = api_key
        self._http = http
        self._index: dict[tuple[str, str], tuple[dict, dict[str, dict]]] = {}

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
        body = {"customer": self.customer, "requestedDate": requested.isoformat(), "products": ids}
        http = self._http or httpx.Client(timeout=30)
        try:
            r = http.post(f"{self.base_url}/api/{endpoint}", json=body, headers={"X-API-Key": self._api_key})
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
            head, rows = {}, {}
            for f in sorted(d.glob("*.json")):
                resp = json.loads(f.read_text())["response"]
                head = {k: v for k, v in resp.items() if k != "products"}
                rows.update({x["productId"]: x for x in resp["products"]})
            self._index[key] = (head, rows)
        head, rows = self._index[key]
        missing = [i for i in ids if i not in rows]
        if missing:
            raise ReplayMiss(f"no recorded {endpoint} answer for {missing} on {requested}, run make record")
        return {**head, "products": [rows[i] for i in ids]}
