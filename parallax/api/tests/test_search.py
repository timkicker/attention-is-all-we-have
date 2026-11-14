"""GET /api/search with the Wikimedia layer replaced by recorded responses (offline)."""

import json
from pathlib import Path

import pytest

from pipeline import wapi

DATA = json.loads((Path(__file__).parent / "recorded" / "search.json").read_text())


@pytest.fixture
def fake_wiki(monkeypatch):
    calls = []

    def get(url, params=None, **kw):
        calls.append((url, params))
        if params.get("action") == "wbgetentities":
            ids = params["ids"].split("|")
            return {"entities": {q: v for q, v in DATA["entities"]["entities"].items() if q in ids}}
        if "en.wikipedia" in url and params.get("generator") == "prefixsearch":
            return DATA["en_prefix"]
        return {"batchcomplete": True}

    monkeypatch.setattr(wapi, "get", get)
    return calls


def test_search_statuses(client, fake_wiki):
    r = client.get("/api/search", params={"q": "Mannerheim"})
    assert r.status_code == 200
    res = r.json()["results"]
    assert [x["qid"] for x in res] == ["Q155093", "Q3565646", "Q999999"]  # the disambiguation page is left out
    line = res[0]
    assert line["title"] == "Mannerheim Line" and line["fi_title"] == "Mannerheim-linja"
    assert line["status"] == "new" and line["eta_s"] > 0
    assert res[2]["status"] == "no_finnish" and res[2]["fi_title"] is None and res[2]["eta_s"] is None
    assert len(fake_wiki) == 2  # one search, one Wikidata request


def test_search_ready_for_loaded_topic(client, monkeypatch, fake_wiki):
    ww = {"Q134949": {"labels": {"en": {"value": "Winter War"}}, "descriptions": {"en": {"value": "war"}},
                      "sitelinks": {"fiwiki": {"title": "Talvisota"}, "enwiki": {"title": "Winter War"}}}}  # fmt: skip
    page = {"query": {"pages": [{"title": "Winter War", "index": 1, "pageprops": {"wikibase_item": "Q134949"}}]}}
    monkeypatch.setattr(wapi, "get", lambda url, params=None, **kw: {"entities": ww} if "ids" in params else page)
    (hit,) = client.get("/api/search", params={"q": "Winter War"}).json()["results"]
    assert hit["status"] == "ready" and hit["eta_s"] is None


def test_search_rate_limited(client, monkeypatch):
    def get(url, params=None, **kw):
        raise wapi.RateLimited("429", 120)

    monkeypatch.setattr(wapi, "get", get)
    r = client.get("/api/search", params={"q": "Sibelius"})
    assert r.status_code == 429
    assert r.headers["Retry-After"] == "120"
    assert r.json()["error"]["code"] == "rate_limited" and r.json()["error"]["retry_after_s"] == 120
    monkeypatch.setattr(wapi, "_cooldown_until", 0.0)


def test_search_needs_q(client):
    assert client.get("/api/search").status_code == 422
