"""Spend Pass revocation: the kitchen's list, checked on every presentation (MCP and /agent/v1) and on approve.
`make revoke PASS=M-1` writes it and a ledger entry."""

import importlib.util
from pathlib import Path

import pytest
from conftest import CODE
from fastapi.testclient import TestClient
from mcp import Client

from validio.agent.holder import Holder
from validio.api import tools
from validio.api.app import app
from validio.api.mcp_server import server
from validio.demo import seed

REASON = "Spend Pass M-1 was revoked by the kitchen"
SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "revoke_pass.py"
MILK = [{"text": "1000 litres of lactose-free milk by Monday"}]


def revoke_cli(*args: str) -> int:
    spec = importlib.util.spec_from_file_location("revoke_pass", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.main(list(args))


@pytest.fixture
def holder(ctx):
    return Holder.from_seed(lambda: tools.nonce(ctx), ctx.db_path, ctx.keys_dir)


def ask(client, holder, key, lines=MILK):
    return client.post("/agent/v1/requests", headers={"Authorization": f"SD-JWT {holder.presentation()}"},
                       json={"lines": lines, "deliverBy": "2026-11-16", "idempotencyKey": key})


def test_revoked_pass_refused_over_http(ctx, holder):
    with TestClient(app) as client:
        assert ask(client, holder, "before").status_code == 200
        assert revoke_cli("M-1") == 0
        r = ask(client, holder, "after")
    assert r.status_code == 401 and r.json()["detail"] == REASON


@pytest.mark.asyncio
async def test_revoked_pass_refused_over_mcp(ctx, holder):
    assert revoke_cli("M-1") == 0
    async with Client(server) as c:
        r = await c.call_tool("request_supply", {"spendPass": holder.presentation(), "lines": MILK,
                                                 "idempotencyKey": "mcp-revoked", "deliverBy": "2026-11-16"})
    assert r.is_error and f"401 Spend Pass refused: {REASON}" in " ".join(getattr(x, "text", "") for x in r.content)


def test_waiting_order_under_a_revoked_pass_is_not_approved(ctx, holder):
    with TestClient(app) as client:
        client.post("/api/demo/stock-out")
        req = ask(client, holder, "mozz", [{"productId": "466375", "quantity": 200, "unit": "BAG"}]).json()
        assert req["status"] == "waiting"
        assert revoke_cli("M-1") == 0
        r = client.post(f"/api/orders/{req['orderId']}/approve", headers={"X-Approve-Code": CODE})
        assert r.status_code == 409 and REASON in r.json()["detail"]
        assert client.get(f"/api/orders/{req['orderId']}").json()["state"] == "waiting"
        led = client.get("/api/ledger").json()
    assert led["chain"]["ok"] is True
    kinds = [(e["kind"], e["sentence"]) for e in led["entries"]][-2:]
    assert kinds[0][0] == "revocation" and kinds[1] == ("decision", f"Approval refused: {REASON}.")


def test_revoke_writes_one_ledger_entry(ctx, capsys):
    assert revoke_cli("M-1") == 0
    assert revoke_cli("M-1") == 0  # again: nothing new
    out = capsys.readouterr().out
    assert "revoked Spend Pass M-1" in out and "already revoked" in out
    entries = [e for e in ctx.audit.list() if e.kind == "revocation"]
    assert [(e.actor, e.mandate_id, e.sentence) for e in entries] == [
        ("kitchen", "M-1", ("The kitchen revoked Spend Pass M-1. Validio refuses it from now on, also to approve "
                            "its waiting orders."))]
    assert ctx.audit.verify().ok and ctx.store.is_revoked("M-1") and not ctx.store.is_revoked("M-2")


def test_revoke_needs_a_pass_id(ctx, capsys):
    with pytest.raises(SystemExit):
        revoke_cli()
    assert revoke_cli("") == 2
    assert not [e for e in ctx.audit.list() if e.kind == "revocation"]


def test_make_revoke_target():
    mk = (Path(__file__).resolve().parents[3] / "Makefile").read_text()
    assert "revoke:" in mk and "revoke_pass.py $(PASS)" in mk


def test_steady_renew_under_a_revoked_pass_is_refused(ctx):
    with TestClient(app) as client:
        assert revoke_cli(seed.STEADY_PASS_ID) == 0  # Steady Orders run on their own weekly pass (review 3 M1)
        r = client.post("/api/steady/S-1/renew", headers={"X-Approve-Code": CODE})
    assert r.status_code == 401 and r.json()["detail"] == REASON.replace("M-1", seed.STEADY_PASS_ID)
