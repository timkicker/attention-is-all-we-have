"""POST /api/demo/ask: the kitchen's agent inside the server, on any text. The fake model without a key,
Gemini with one. Locally the kitchen gate is enough; with VALIDIO_PUBLIC_READ=1 the demo token too."""

from conftest import TOKEN
from test_api import client  # noqa: F401


def ask(client, text, **headers):  # noqa: F811
    return client.post("/api/demo/ask", json={"text": text}, headers=headers)


def test_free_text_becomes_a_request(client):  # noqa: F811
    r = ask(client, "500 litres of lactose-free milk by Monday")
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["requestId"] == "R-1"
    assert out["model"].startswith("fake model")
    assert any("agent -> request_supply" in ln for ln in out["lines"])
    assert out["final"]
    assert [i["id"] for i in client.get("/api/inbox").json()] == ["R-1"]
    kinds = [e["kind"] for e in client.get("/api/ledger").json()["entries"]]
    assert "request" in kinds


def test_unrecorded_product_answers_cleanly(client):  # noqa: F811
    r = ask(client, "20 kg of salmon by Monday")  # salmon is not in any recording
    assert r.status_code == 200, r.text
    out = r.json()
    assert "requestId" not in out
    assert out["final"].startswith("Validio could not take the request, nothing ordered.")
    assert "no recorded" in out["final"]
    assert any("503 no recorded answers" in ln for ln in out["lines"])
    assert client.get("/api/inbox").json() == []


def test_empty_text_is_refused(client):  # noqa: F811
    assert ask(client, "  ").status_code == 422


def test_public_read_needs_the_demo_token(client, monkeypatch):  # noqa: F811
    monkeypatch.setenv("VALIDIO_PUBLIC_READ", "1")
    assert ask(client, "500 litres of lactose-free milk by Monday").status_code == 403
    r = ask(client, "500 litres of lactose-free milk by Monday", **{"X-Demo-Token": TOKEN})
    assert r.status_code == 200, r.text
