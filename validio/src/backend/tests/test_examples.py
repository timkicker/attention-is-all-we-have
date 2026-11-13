"""validio/examples: the third-party client does scene 2 over /agent/v1 on the in-process server, and
the MCP config snippet points at the mounted /mcp path."""

import importlib.util
import json
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from validio.api.app import app

EXAMPLES = Path(__file__).resolve().parents[3] / "examples"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, EXAMPLES / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _pass_files(ctx, tmp_path):
    con = sqlite3.connect(ctx.db_path)
    (issuance,) = con.execute("select issuance from spend_pass where id = 'M-1'").fetchone()
    con.close()
    (tmp_path / "pass.txt").write_text(issuance)
    return tmp_path / "pass.txt", Path(ctx.keys_dir) / "agent-es256.json"


def test_python_client_places_scene2_order(ctx, tmp_path):
    client = _load("agent_client")
    pass_file, key_file = _pass_files(ctx, tmp_path)
    with TestClient(app) as http:
        order = client.scene2(http, pass_file.read_text(), key_file.read_text())
    assert order["state"] == "placed"
    assert [(ln["productId"], ln["quantity"]) for ln in order["lines"]] == [("464306", 1000)]
    assert order["totalCents"] == 101000


def test_python_client_shows_only_three_fields(ctx, tmp_path):
    client = _load("agent_client")
    pass_file, key_file = _pass_files(ctx, tmp_path)
    with TestClient(app) as http:
        token = client.presentation(pass_file.read_text(), key_file.read_text(),
                                    http.get("/agent/v1/nonce").json()["nonce"])
    disclosed = [json.loads(client.b64d(d))[1] for d in token.split("~")[1:-1]]
    assert sorted(disclosed) == ["autoLimitCents", "diet", "hardCapCents"]


def test_mcp_config_points_at_streamable_http():
    cfg = json.loads((EXAMPLES / "mcp.json").read_text())
    (server,) = cfg["mcpServers"].values()
    assert server["type"] == "http" and server["url"] == "http://127.0.0.1:8410/mcp/"
