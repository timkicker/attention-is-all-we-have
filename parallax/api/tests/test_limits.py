"""Audit guards: what a visitor types stays theirs, checks are bounded and scoped, errors keep the contract."""

import json

from api import ratelimit, sqllog
from api.tests.conftest import schema_errors
from contract.engine import FIXTURES

ANSWER = next(iter(json.loads((FIXTURES / "split.json").read_text(encoding="utf-8")).values()))["text"]


def test_pasted_answer_is_not_kept_for_other_visitors(client):
    r = client.post("/api/check", json={"text": ANSWER})
    assert r.status_code == 200, r.text
    run_id = r.json()["run_id"]
    panel = client.get("/api/sql/check")
    assert panel.status_code == 404
    assert run_id not in json.dumps(sqllog.LAST) and ANSWER[:40] not in json.dumps(sqllog.LAST)


def test_long_parameters_are_logged_as_their_length():
    shown = sqllog._shown_params({"text": "x" * 500, "q": "short", "hs": ("a", "b")})
    assert shown == {"text": {"chars": 500}, "q": "short", "hs": {"count": 2}}


def test_check_rejects_unknown_editions(client):
    r = client.post("/api/check", json={"text": ANSWER, "langs": ["fi", "xx"]})
    assert r.status_code == 422 and r.json()["error"]["code"] == "bad_lang"
    assert client.post("/api/check", json={"text": ANSWER, "langs": ["fi"] * 17}).status_code == 422


def test_check_unknown_topic_is_404(client):
    r = client.post("/api/check", json={"text": ANSWER, "topic": "no-such-topic"})
    assert r.status_code == 404 and r.json()["error"]["code"] == "topic_not_found"


def test_check_within_a_topic_quotes_only_that_topic(client):
    r = client.post("/api/check", json={"text": ANSWER, "topic": "winterwar"})
    assert r.status_code == 200, r.text
    assert not schema_errors("/api/check", r.json(), method="post")
    rows = sqllog.run("SELECT lang, page_id FROM page WHERE topic_id = 'winterwar'")
    pages = {(p["lang"], p["page_id"]) for p in rows}
    evidence = [e for c in r.json()["claims"] for v in c["per_lang"].values() for e in v["evidence"]]
    assert evidence and all((e["lang"], e["page_id"]) in pages for e in evidence)


def test_topics_name_the_newest_stored_revision(client):
    body = client.get("/api/topics").json()
    assert not schema_errors("/api/topics", body)
    eds = [e for t in body["topics"] for e in t["editions"] if e["revisions"]]
    assert eds and all(e["last_ts"] and e["last_ts"] >= e["first_ts"] for e in eds)


def test_unexpected_error_keeps_the_error_shape(client, monkeypatch):
    from fastapi.testclient import TestClient

    from api.main import app
    from api.routes import topics

    def boom(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setenv("INGEST_WORKER", "0")
    monkeypatch.setattr(topics.sqllog, "run_file", boom)
    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.get("/api/stats")
    assert r.status_code == 500
    assert r.json() == {"error": {"code": "internal", "message": "Something went wrong on our side."}}


def test_limit_refills_over_time():
    now = [0.0]
    lim = ratelimit.Limit("t", per_minute=60, burst=2, clock=lambda: now[0])
    assert lim.take("a") == 0 and lim.take("a") == 0
    assert lim.take("a") > 0  # burst used up
    assert lim.take("b") == 0  # another visitor has their own bucket
    now[0] += 1.0
    assert lim.take("a") == 0


def test_limited_requests_get_429_too_many(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMITS", "1")
    monkeypatch.setenv("RATE_SEARCH", "1/1")
    ratelimit.reset()
    try:
        from pipeline import wapi

        monkeypatch.setattr(wapi, "get", lambda url, params=None, **kw: {"batchcomplete": True})
        assert client.get("/api/search", params={"q": "limit probe a"}).status_code == 200
        r = client.get("/api/search", params={"q": "limit probe b"})
        assert r.status_code == 429 and r.json()["error"]["code"] == "too_many" and int(r.headers["Retry-After"]) >= 1
    finally:
        ratelimit.reset()
