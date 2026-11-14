"""Play audit 6: the simulated stock-out goes off again, with its own ledger entry."""

from conftest import TOKEN
from test_api import client  # noqa: F401

H = {"X-Demo-Token": TOKEN}


def sims(client):  # noqa: F811
    return [e["sentence"] for e in client.get("/api/ledger").json()["entries"] if e["kind"] == "simulation"]


def test_on_then_off(client):  # noqa: F811
    assert client.post("/api/demo/stock-out", headers=H).json()["stockOut466375"] is True
    r = client.post("/api/demo/stock-out", headers=H, json={"on": False})
    assert r.status_code == 200 and r.json()["stockOut466375"] is False
    assert client.get("/api/demo").json()["stockOut466375"] is False
    on, off = sims(client)
    assert on.startswith("Simulated a stock-out of")
    assert off.startswith("Ended the simulated stock-out of") and "11,603" in off
    assert client.get("/api/ledger").json()["chain"]["ok"]


def test_same_state_twice_writes_nothing(client):  # noqa: F811
    client.post("/api/demo/stock-out", headers=H, json={"on": False})
    assert sims(client) == []
    client.post("/api/demo/stock-out", headers=H, json={"on": True})
    client.post("/api/demo/stock-out", headers=H, json={"on": True})
    assert len(sims(client)) == 1
