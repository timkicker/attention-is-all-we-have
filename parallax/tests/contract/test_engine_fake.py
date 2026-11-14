"""The fake engine is deterministic, offline and answers the demo path from the fixtures."""

import json

import numpy as np
import pytest

from contract.engine import (
    DIM,
    FIXTURES,
    LABELS,
    Candidate,
    FakeEngine,
    claim_hash,
    get_engine,
    normalise,
    split_sentences,
)

FAKE = FakeEngine()


def test_claim_hash():
    assert claim_hash("  Talvisota   ALKOI\n1939. ") == claim_hash("talvisota alkoi 1939.")
    assert len(claim_hash("x")) == 16 and int(claim_hash("x"), 16) >= 0
    assert normalise("Á") == "á"


def test_embed_unit_vectors_twice_the_same():
    texts = ["The Winter War began on 30 November 1939.", "Talvisota alkoi 30. marraskuuta 1939."]
    a, b = FAKE.embed(texts), FAKE.embed(texts)
    assert a == b
    for v in a:
        assert len(v) == DIM
        assert abs(np.linalg.norm(v) - 1) < 1e-6
    assert a[0] != a[1]


def test_embed_fixture_vectors():
    for item in json.loads((FIXTURES / "embed.json").read_text()).values():
        (v,) = FAKE.embed([item["text"]])
        assert len(v) == DIM and abs(np.linalg.norm(v) - 1) < 1e-3


def test_split_fixture_and_fallback():
    for item in json.loads((FIXTURES / "split.json").read_text()).values():
        assert FAKE.split_claims(item["text"]) == item["claims"]
    text = "Talvisota alkoi 30. marraskuuta 1939. Sota päättyi 12. maaliskuuta 1940 Moskovan rauhaan."
    assert FAKE.split_claims(text, "fi") == split_sentences(text)
    assert split_sentences(text) == [
        "Talvisota alkoi 30. marraskuuta 1939.",
        "Sota päättyi 12. maaliskuuta 1940 Moskovan rauhaan.",
    ]


def test_judge_fixture_and_fallback():
    judge = json.loads((FIXTURES / "judge.json").read_text())
    assert {v["label"] for v in judge.values()} <= set(LABELS)
    claim = (
        "Neuvostoliitto lavasti 26. marraskuuta 1939 Mainilan laukaukset , "
        "joilla se perusteli sotaa puolustuksellisena toimenpiteenä."
    )
    assert claim_hash(claim) == "8519fbaf22d33984"
    cands = [
        Candidate(
            "en", 33924, "a3b291dafd10d41b", "On 26 November 1939, an incident was reported near the Soviet village"
        ),
        Candidate("de", 51245, "0000000000000000", claim.upper()),
        Candidate("de", 51245, "0000000000000001", "Something else entirely."),
    ]
    v = FAKE.judge(claim, "fi", cands)
    assert [x.h for x in v] == [c.h for c in cands]
    assert v[0].label == "partial" and v[0].terms == [("lavasti", "reported")]
    assert v[1].label == "same" and v[2].label == "different"


def test_gloss():
    gloss = json.loads((FIXTURES / "gloss.json").read_text())
    assert gloss
    assert FAKE.gloss(["Jotain aivan muuta."], "fi") == ["[no gloss] Jotain aivan muuta."]


def test_get_engine(monkeypatch):
    monkeypatch.setenv("ENGINE", "fake")
    e = get_engine()
    assert isinstance(e, FakeEngine) and e.name == "fake"
    assert e.model_id and e.prompt_version == "judge-v1"
    monkeypatch.setenv("ENGINE", "nonsense")
    with pytest.raises(ValueError):
        get_engine()


def test_fixture_files_present():
    for name in ("embed", "split", "judge", "gloss"):
        assert (FIXTURES / f"{name}.json").exists()
