"""Pieces of the any-article ingest that need no database or network."""

import datetime as dt

import numpy as np

from contract.engine import FAKE_GUESS_MODEL, Candidate, FakeEngine, guess_verdicts, sketch_embed
from pipeline import job, wapi


def test_slug_is_lowercase_qid():
    assert job.topic_slug("Q155093") == "q155093"


def test_estimate_grows_with_size_and_since_is_faster():
    small, big = job.estimate_s(5_000, 7), job.estimate_s(150_000, 7)
    assert 15 < small < big
    assert job.estimate_s(150_000, 7, "2021-01-01") < big


def test_job_view_orders_editions_and_reports_rate_limit():
    t = dt.datetime(2026, 11, 14, 12, 0, 0)
    j = {"qid": "Q1", "topic_id": "q1", "title": "X", "state": "running", "since": None, "eta_s": 100,
         "started_at": t}  # fmt: skip
    eds = [
        {"lang": "ru", "state": "failed", "pct": 35, "error": "rate_limited", "retry_at": t},
        {"lang": "fi", "state": "done", "pct": 90, "error": None, "retry_at": None},
    ]
    v = job.job_view(j, eds)
    assert [e["lang"] for e in v["editions"]] == list(job.LANGS)
    ru = v["editions"][4]
    assert ru["error"] == "rate_limited" and ru["retry_at"] == "2026-11-14T12:00:00Z"
    assert v["editions"][0]["pct"] == 100
    assert v["editions"][1] == {"lang": "sv", "state": "failed", "pct": 0, "error": "no_article", "retry_at": None}


def test_sketch_embed_deterministic_and_cross_language():
    a, b, c = sketch_embed(
        [
            "Linjan pituus oli 132 kilometriä ja sen rakensi Johan Enckell vuonna 1927.",
            "The line was 132 kilometres long and was built by Johan Enckell in 1927.",
            "Sibelius sävelsi Finlandian.",
        ]
    )
    assert abs(np.linalg.norm(a) - 1) < 1e-9 and sketch_embed(["x" * 30])[0] == sketch_embed(["x" * 30])[0]
    assert np.dot(a, b) > np.dot(a, c) + 0.2


def test_guess_verdicts_and_fixture_first():
    claim = "Linjan pituus oli 132 kilometriä ja sen rakennutti Johan Enckell vuonna 1927."
    cands = [
        Candidate("sv", 1, "0" * 16, "Linjen var 135 kilometer lång och byggdes av Johan Enckell 1927."),
        Candidate("sv", 1, "1" * 16, "Helt annat innehåll i denna mening."),
    ]
    v = guess_verdicts(claim, cands)
    assert v[0].label == "partial" and v[0].numbers == [("132", "135")]
    assert v[1].label == "different"
    out = FakeEngine().judge_or_guess(claim, "fi", cands)
    assert [m for _, m in out] == [FAKE_GUESS_MODEL, FAKE_GUESS_MODEL]


def test_rate_limited_sets_cooldown(monkeypatch):
    class Resp:
        status_code = 429
        headers = {"Retry-After": "0"}

    monkeypatch.setattr(wapi.SESSION, "get", lambda *a, **k: Resp())
    monkeypatch.setattr(wapi.time, "sleep", lambda s: None)
    monkeypatch.setattr(wapi, "_cooldown_until", 0.0)
    waits = []
    wapi.on_wait(waits.append)
    try:
        wapi.get("https://example.invalid/never-cached", {"x": dt.datetime.now().isoformat()})
    except wapi.RateLimited as e:
        assert e.retry_after_s == wapi.GIVE_UP_COOLDOWN_S
    else:
        raise AssertionError("no RateLimited")
    finally:
        wapi.on_wait(None)
    assert len(waits) == wapi.MAX_429_TRIES - 1
    assert wapi.cooldown_left() > 100
    monkeypatch.setattr(wapi, "_cooldown_until", 0.0)
