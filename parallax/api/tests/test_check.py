import json
import os

import pytest

from api.tests.conftest import schema_errors
from contract.engine import FIXTURES

ANSWER = next(iter(json.loads((FIXTURES / "split.json").read_text(encoding="utf-8")).values()))["text"]


@pytest.fixture(scope="module")
def run(client):
    r = client.post("/api/check", json={"text": ANSWER})
    assert r.status_code == 200, r.text
    return r.json()


def labels(run, idx):
    return {lang: v["label"] for lang, v in run["claims"][idx]["per_lang"].items()}


def test_matches_contract(run):
    assert not schema_errors("/api/check", run, method="post")
    assert run["source"] == "live" and run["engine"] == "fake"
    assert [c["text"] for c in run["claims"]][0].startswith("The Shelling of Mainila on 26 November 1939 was staged")


def test_mainila_answer_says_and_stopped_saying(run):
    staged = labels(run, 0)
    assert staged["en"] == "stopped_saying"
    assert staged["fi"] == staged["de"] == staged["sv"] == "says"
    en = run["claims"][0]["per_lang"]["en"]["evidence"][0]
    assert en["h"] == "7aee25bc3466a2fc" and en["died"] == "2009-12-31T20:28:48Z" and en["died_rev"] == 335165674
    assert en["oldid_url"] == "https://en.wikipedia.org/w/index.php?oldid=33225464"
    all_labels = [x for i in range(len(run["claims"])) for x in labels(run, i).values()]
    assert "says" in all_labels and "stopped_saying" in all_labels and "not_found" in all_labels


def test_one_statement_per_claim_uses_the_vector_index(run):
    nearest = [s for s in run["sql"] if "VEC_DISTANCE_COSINE" in s["text"]]
    assert len(nearest) == len(run["claims"])
    assert all("FOR SYSTEM_TIME ALL" in s["text"] and s["index"] == "emb" for s in nearest)


def test_replay_returns_the_same_json_without_the_engine(client, run, monkeypatch):
    import contract.engine

    def boom():
        raise AssertionError("replay must not call the engine")

    monkeypatch.setattr(contract.engine, "get_engine", boom)
    again = client.get(f"/api/check/{run['run_id']}").json()
    assert not schema_errors("/api/check/{run_id}", again)
    assert {k: v for k, v in again.items() if k != "sql"} == {k: v for k, v in run.items() if k != "sql"}


def test_replay_at_an_earlier_date_relabels(client, run):
    old = client.get(f"/api/check/{run['run_id']}", params={"as_of": "2008-01-01"}).json()
    assert labels(old, 0)["en"] == "says"
    assert labels(old, 0)["fi"] != "says"  # the fi sentence was added in 2026


def test_as_of_in_the_request(client):
    r = client.post("/api/check", json={"text": ANSWER, "as_of": "2008-01-01", "langs": ["en", "de"]}).json()
    assert labels(r, 0) == {"de": "not_found", "en": "says"}  # de matched only from 2013 on
    assert set(r["claims"][0]["per_lang"]) == {"de", "en"}


def test_recorded_runs(client):
    from api import record_checks

    run_id = record_checks.record(record_checks.fixture_answers()[0])
    assert run_id == record_checks.record(record_checks.fixture_answers()[0])  # recording again replaces
    body = client.get("/api/check/recorded").json()
    assert not schema_errors("/api/check/recorded", body)
    (rec,) = [r for r in body["runs"] if r["run_id"] == run_id]
    assert rec["answer_model"] == record_checks.FIXTURE_MODEL
    replay = client.get(f"/api/check/{run_id}").json()
    assert replay["source"] == "recorded" and labels(replay, 0)["en"] == "stopped_saying"


def test_record_if_empty_leaves_existing_runs(client, monkeypatch, capsys):
    from api import record_checks

    record_checks.record(record_checks.fixture_answers()[0])
    monkeypatch.setattr("sys.argv", ["record_checks", "--if-empty", "--fixture"])
    monkeypatch.setattr(record_checks, "record", lambda a: pytest.fail("recorded although runs exist"))
    assert record_checks.main() == 0
    assert "nothing to record" in capsys.readouterr().out


def test_unknown_run_is_404(client):
    r = client.get("/api/check/zzzzzzzzzzzz")
    assert r.status_code == 404 and r.json()["error"]["code"] == "run_not_found"


def test_empty_text_is_422(client):
    r = client.post("/api/check", json={"text": "   "})
    assert r.status_code == 422
    assert not schema_errors("/api/check", r.json(), method="post", status="422")


@pytest.mark.skipif(
    os.environ.get("CHECK_REAL_SMOKE") != "1", reason="manual: ENGINE=real smoke test with a Gemini key"
)
def test_real_engine_smoke(monkeypatch):
    # CHECK_REAL_SMOKE=1 with GEMINI_API_KEY in the environment; needs engine.real from Track A (A9).
    import time

    from fastapi.testclient import TestClient

    from api.main import app

    monkeypatch.setenv("ENGINE", "real")
    with TestClient(app) as c:
        t0 = time.perf_counter()
        r = c.post("/api/check", json={"text": ANSWER})
        took = time.perf_counter() - t0
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["engine"] == "real" and len(body["claims"]) >= 2
    assert took < 15, f"{took:.1f} s"
