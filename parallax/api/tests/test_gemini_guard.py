import time

import pytest

from api import gemini_guard as g


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    g.reset()
    yield
    g.reset()


def test_answer_within_budget():
    assert g.Budget(5).call(lambda x: x + 1, 1) == 2


def test_slow_call_falls_back(monkeypatch):
    monkeypatch.setattr(g, "CALL_S", 0.2)
    t = time.monotonic()
    assert g.Budget(5).call(time.sleep, 2) is None
    assert time.monotonic() - t < 1


def test_spent_budget_skips_the_call():
    called = []
    assert g.Budget(0).call(called.append, 1) is None
    assert called == []


def test_failure_falls_back():
    def boom():
        raise RuntimeError("429")

    assert g.Budget(5).call(boom) is None


def test_breaker_opens_after_repeated_failures(monkeypatch):
    monkeypatch.setattr(g, "BREAKER_FAILS", 3)

    def boom():
        raise RuntimeError("503")

    for _ in range(3):
        g.Budget(5).call(boom)
    called = []
    assert g.Budget(5).call(called.append, 1) is None
    assert called == [] and not g.available()


def test_daily_cap(monkeypatch):
    monkeypatch.setattr(g, "DAILY_CAP", 2)
    b = g.Budget(5)
    assert b.call(lambda: 1) == 1 and b.call(lambda: 2) == 2
    assert b.call(lambda: 3) is None
    assert g.status()["calls_today"] == 2


def test_check_falls_back_to_the_guess_when_gemini_fails(monkeypatch):
    """A live check with the real engine still answers when every Gemini call fails, labelled with the guess model."""
    from api import checker
    from contract.engine import FAKE_GUESS_MODEL, Candidate

    class Broken:
        name = "real"
        model_id = "gemini-test"
        prompt_version = "judge-v1"

        def split_claims(self, text, lang=None):
            raise RuntimeError("quota")

        def judge(self, claim, lang, cs):
            raise RuntimeError("quota")

    row = {
        "lang": "fi",
        "page_id": 1,
        "h": "a" * 16,
        "text": "Talvisota alkoi 30. marraskuuta 1939.",
        "row_start": checker.MAX_TS,
        "row_end": checker.MAX_TS,
        "died_rev": None,
        "died_comment": None,
        "born_rev": 1,
        "dist": 0.1,
    }
    out = checker._judge_claim(Broken(), "The Winter War began on 30 November 1939.", {"fi": [row]}, g.Budget(5))
    assert [e["verdict"]["model"] for e in out["fi"]] == [FAKE_GUESS_MODEL]
    assert Candidate  # imported for the row shape
