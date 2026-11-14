"""`validio-agent`: the pane as a command, plus --print-pass for a third-party agent."""

import sqlite3
import tomllib
from pathlib import Path

from validio.agent import cli


def test_entry_point_declared():
    toml = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text())
    assert toml["project"]["scripts"]["validio-agent"] == "validio.agent.cli:main"


def test_print_pass_prints_the_issued_pass(ctx, capsys):
    assert cli.main(["--print-pass"]) == 0
    (issuance,) = sqlite3.connect(ctx.db_path).execute("select issuance from spend_pass").fetchone()
    assert capsys.readouterr().out.strip() == issuance


def test_local_scene4_prints_pane_and_writes_transcript(catalog, tmp_path, capsys, monkeypatch):
    from validio.api.state import set_ctx

    monkeypatch.setattr(cli, "ARTIFACTS", tmp_path)
    monkeypatch.setenv("VALIDIO_DB", str(tmp_path / "unused.db"))  # restored after; --local sets its own
    monkeypatch.setenv("VALIDIO_KEYS", str(tmp_path / "unused-keys"))
    set_ctx(None)
    assert cli.main(["--scene", "4", "--local"]) == 0
    out = capsys.readouterr().out
    assert "agent -> renew_steady_order" in out and "waits for the owner:" in out
    assert (tmp_path / "scene-4.md").is_file()
    set_ctx(None)


def test_pair_with_a_kitchen_account_then_present_its_pass(ctx, tmp_path, monkeypatch):
    """--kitchen and --pair: the agent answers the account's pairing code with its own key, waits for Allow,
    keeps the pass, and its presentations then pass the account's gate (also over the public link)."""
    from fastapi.testclient import TestClient

    from validio.api import accounts as acc_mod

    monkeypatch.setenv("VALIDIO_ACCOUNTS", str(tmp_path / "accounts"))
    monkeypatch.setenv("VALIDIO_TEMPLATE", str(tmp_path / "template"))
    acc_mod._tries.clear()
    from validio.api.app import app

    with TestClient(app) as web, TestClient(app) as agent:
        kitchen = web.post("/api/account/demo").json()["id"]
        code = web.post("/api/agent/pair").json()["pairing"]["code"]
        keys = tmp_path / "agent"
        assert cli.send_pair(agent, kitchen, code, keys) == "consent"
        assert web.get("/api/agent").json()["consent"]["name"] == cli.AGENT_NAME
        assert cli.wait_pass(agent, kitchen, code, keys, timeout=0) is None  # not allowed yet
        assert web.post("/api/agent/allow").json()["state"] == "active"
        assert cli.wait_pass(agent, kitchen, code, keys, timeout=5) == (keys / "pass.sdjwt").read_text()
        holder = cli.kitchen_holder(agent, kitchen, keys)
        r = agent.post(f"/agent/v1/k/{kitchen}/requests", headers={"Authorization": f"SD-JWT {holder.presentation()}"},
                       json={"lines": [{"text": "1000 litres of lactose-free milk by Monday, budget 1200 euro"}],
                             "deliverBy": "2026-11-16", "idempotencyKey": "cli-pair-test"})
        assert r.status_code == 200, r.text
        assert r.json()["id"] == "R-1"
        # the account's own nonce, MCP under the account's path
        assert cli.kitchen_urls("https://x.modal.run/", kitchen) == (
            f"https://x.modal.run/mcp/k/{kitchen}/", f"https://x.modal.run/agent/v1/k/{kitchen}")
