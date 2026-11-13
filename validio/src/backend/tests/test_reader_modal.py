"""Step 18, the Gemma reader on Modal: client side (respx) and the /read app (TestClient, fake vLLM)."""

import json
import sys
from pathlib import Path

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from validio.audit.log import AuditLog
from validio.reader import FakeReader, ReaderResult, read, reader_from_env
from validio.reader.remote import ModalReader

sys.path.insert(0, str(Path(__file__).parents[2] / "cloud"))
import reader_api

URL = "https://reader.example.modal.run"
TOKEN = "t0ken-for-tests"
PLANTED = json.loads((Path(__file__).parents[1] / "validio/demo/planted.json").read_text())[0]["text"]
GOOD = {"flags": [{"code": "addresses_agents", "text": "AI agents"}], "summary": "Talks to AI agents."}


@respx.mock
def test_modal_reader_parses_schema():
    route = respx.post(f"{URL}/read").mock(return_value=httpx.Response(200, json=GOOD))
    got = read(PLANTED, reader=ModalReader(URL, TOKEN))
    assert got.reader == "modal" and not got.fell_back
    assert got.result == ReaderResult.model_validate(GOOD)
    req = route.calls.last.request
    assert req.headers["authorization"] == f"Bearer {TOKEN}"
    assert json.loads(req.content) == {"text": PLANTED}


@respx.mock
def test_modal_reader_rejects_extra_fields(tmp_path):
    respx.post(f"{URL}/read").mock(return_value=httpx.Response(200, json={**GOOD, "order": "463047"}))
    ledger = AuditLog(tmp_path / "l.db")
    got = read(PLANTED, reader=ModalReader(URL, TOKEN), ledger=ledger)
    assert got.fell_back and got.result == FakeReader().read(PLANTED)
    assert ledger.list()[0].kind == "reader_fallback"


@respx.mock
def test_modal_reader_falls_back_on_timeout(tmp_path):
    respx.post(f"{URL}/read").mock(side_effect=httpx.ReadTimeout("slow"))
    ledger = AuditLog(tmp_path / "l.db")
    got = read(PLANTED, reader=ModalReader(URL, TOKEN), ledger=ledger, product_id="463047")
    assert got.fell_back and got.reader == "fake"
    assert "ReadTimeout" in ledger.list()[0].sentence


@respx.mock
def test_modal_reader_falls_back_on_401():
    respx.post(f"{URL}/read").mock(return_value=httpx.Response(401))
    assert read(PLANTED, reader=ModalReader(URL, "wrong")).fell_back


def test_modal_reader_without_url_falls_back():
    assert read(PLANTED, reader=ModalReader("", "")).fell_back


def test_reader_mode_modal_from_env(monkeypatch):
    monkeypatch.setenv("READER_MODE", "modal")
    monkeypatch.setenv("MODAL_GEMMA_URL", URL)
    monkeypatch.setenv("MODAL_GEMMA_TOKEN", TOKEN)
    r = reader_from_env(None)
    assert isinstance(r, ModalReader) and r.url == URL


# the app that runs next to vLLM on Modal


def fake_vllm(answer):
    calls = []

    def chat(body):
        calls.append(body)
        return {"choices": [{"message": {"content": answer if isinstance(answer, str) else json.dumps(answer)}}]}

    return chat, calls


@pytest.fixture
def client_for():
    def make(answer):
        chat, calls = fake_vllm(answer)
        return TestClient(reader_api.make_app(TOKEN, chat)), calls

    return make


def test_read_needs_bearer(client_for):
    c, calls = client_for(GOOD)
    assert c.post("/read", json={"text": PLANTED}).status_code == 401
    assert c.post("/read", json={"text": PLANTED}, headers={"Authorization": "Bearer nope"}).status_code == 401
    assert calls == []


def test_read_returns_fixed_shape(client_for):
    c, calls = client_for(GOOD)
    r = c.post("/read", json={"text": PLANTED}, headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 200
    assert ReaderResult.model_validate(r.json()) == ReaderResult.model_validate(GOOD)
    body = calls[0]
    assert body["response_format"]["type"] == "json_schema"
    assert body["temperature"] == 0
    assert PLANTED in body["messages"][-1]["content"]


def test_read_drops_model_extras(client_for):
    c, _ = client_for({**GOOD, "order": "463047", "flags": [{"code": "approve", "text": "x"}, *GOOD["flags"]]})
    r = c.post("/read", json={"text": PLANTED}, headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 200 and r.json() == GOOD


def test_read_bad_model_answer_is_502(client_for):
    c, _ = client_for("not json at all")
    r = c.post("/read", json={"text": PLANTED}, headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 502


def test_read_limits_text(client_for):
    c, _ = client_for(GOOD)
    r = c.post("/read", json={"text": "x" * 20001}, headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 422


def test_app_schema_matches_backend():
    assert reader_api.FLAG_CODES == {"addresses_agents", "gives_instruction", "mentions_claim"}
