import pytest

from contract.engine import Candidate
from engine import gemini
from engine.real import parse_judge

CANDS = [
    Candidate("de", 1, "aa", "Am 26. November inszenierte die Rote Armee ..."),
    Candidate("en", 2, "bb", "On 26 November 1939, an incident was reported ..."),
]


def test_judge_json_clean():
    data = gemini.parse_json(
        '{"results":[{"i":1,"label":"same","numbers":[],"terms":[["lavasti","inszenierte"]]},'
        '{"i":2,"label":"partial","numbers":[],"terms":[["lavasti","reported"]]}]}'
    )
    v = parse_judge(data, CANDS)
    assert [x.label for x in v] == ["same", "partial"] and v[1].terms == [("lavasti", "reported")]
    assert v[0].h == "aa"


def test_judge_json_with_prose_and_fence():
    raw = (
        'Here is the result:\n```json\n{"results":[{"i":2,"label":"contradicts","numbers":[["26 662","25 904"]]},'
        '{"i":1,"label":"different"}]}\n```\nHope this helps.'
    )
    v = parse_judge(gemini.parse_json(raw), CANDS)
    assert [x.label for x in v] == ["different", "contradicts"] and v[1].numbers == [("26 662", "25 904")]


def test_judge_missing_candidate_or_bad_label_raises():
    with pytest.raises(ValueError):
        parse_judge({"results": [{"i": 1, "label": "same"}, {"i": 2, "label": "biased"}]}, CANDS)


def test_no_json_raises():
    with pytest.raises(ValueError):
        gemini.parse_json("I cannot answer that.")


class _Err(Exception):
    def __init__(self, status):
        self.status_code = status


def test_retries_on_429_then_parses(monkeypatch):
    monkeypatch.setattr(gemini, "_BUCKET", gemini.TokenBucket(10_000))
    answers = [_Err(429), _Err(503), "not json", '{"claims":["a"]}']
    sleeps = []

    def call(_msgs):
        a = answers.pop(0)
        if isinstance(a, Exception):
            raise a
        return a

    data, raw = gemini.ask_json("s", "u", sleep=sleeps.append, call=call)
    assert data == {"claims": ["a"]} and sleeps == [2.0, 4.0]


def test_gives_up_after_five_attempts(monkeypatch):
    monkeypatch.setattr(gemini, "_BUCKET", gemini.TokenBucket(10_000))

    def call(_msgs):
        raise _Err(429)

    with pytest.raises(gemini.GeminiError):
        gemini.ask_json("s", "u", sleep=lambda s: None, call=call)


def test_token_bucket_paces():
    now = [0.0]
    slept = []

    def sleep(s):
        slept.append(s)
        now[0] += s

    b = gemini.TokenBucket(60, clock=lambda: now[0], sleep=sleep)
    for _ in range(12):
        b.take()
    assert now[0] >= 5.9  # 6 burst tokens, then one per second
