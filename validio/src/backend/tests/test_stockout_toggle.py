"""Play audit 6: the simulated stock-out goes off again, with its own ledger entry. It has no route any more;
the template build sets it in the store (scripts/demo_check.py)."""

from asking import ask, stockout
from test_api import client  # noqa: F401


def sims(client):  # noqa: F811
    return [e["sentence"] for e in client.get("/api/ledger").json()["entries"] if e["kind"] == "simulation"]


def test_on_then_off(client):  # noqa: F811
    stockout(on=True)
    assert client.get("/api/demo").json()["stockOut466375"] is True
    stockout(on=False)
    assert client.get("/api/demo").json()["stockOut466375"] is False
    on, off = sims(client)
    assert on.startswith("Simulated a stock-out of")
    assert off.startswith("Ended the simulated stock-out of") and "11,603" in off
    assert client.get("/api/ledger").json()["chain"]["ok"]


def test_stock_out_entries_are_the_demos_own_group(client, ctx):  # noqa: F811
    ask(ctx, "500 litres of lactose-free milk by Monday")
    stockout(on=True)
    stockout(on=False)
    led = client.get("/api/ledger").json()
    assert {e["requestId"] for e in led["entries"] if e["kind"] == "simulation"} == {"demo"}
    assert {"requestId": "demo", "titleText": "Demo"} in led["groups"]
