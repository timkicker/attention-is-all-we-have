"""Any MCP agent, also one that cannot sign (a chat app connector, a coding tool, a script): pairing shows
/mcp/c/<token>/, the first request there asks for consent under the name the MCP client gives (clientInfo, else
"MCP agent"), and after Allow Validio holds the key and signs for it, so its tools take no spendPass. Rules,
approval, Pause and the ledger stay as they are."""

import asyncio
import contextlib
import hashlib
import importlib.util
import json
import re
import socket
import sqlite3
import threading
import time

import pytest
from asking import pair_demo_agent
from fastapi.testclient import TestClient
from test_accounts import SIGNUP, app_env  # noqa: F401
from test_agent_routing import MCP_HEADERS, Mcp, _init

from validio.api import connect
from validio.api.accounts import get_accounts
from validio.config import ROOT

MILK = [{"text": "1000 litres of lactose-free milk"}]
URL = re.compile(r"http://testserver/mcp/c/([A-Za-z0-9_-]{43})/")


@pytest.fixture
def kitchens(app_env):  # noqa: F811
    """A demo copy (Rules saved) and a signed-up kitchen (Rules never saved), neither with an agent."""
    agent_http = TestClient(app_env, base_url="http://127.0.0.1:8410")  # MCP checks the Host header
    with TestClient(app_env) as demo, TestClient(app_env) as new, agent_http as agent:
        a = demo.post("/api/account/demo").json()["id"]
        b = new.post("/api/account/signup", json=SIGNUP).json()["id"]
        yield demo, new, agent, a, b


def start_pairing(web) -> str:
    s = web.post("/api/agent/pair").json()
    m = URL.fullmatch(s["pairing"]["mcpUrl"])
    assert m, s["pairing"]
    return m.group(1)


AGENT = "Kitchen Bot"  # the clientInfo.name the raw MCP client below sends


def connect_app(web, agent, name: str = AGENT) -> str:
    """Connect agent, the MCP agent opens the URL, the kitchen sees its name and allows."""
    token = start_pairing(web)
    Mcp(agent, f"/mcp/c/{token}/", name=name)
    s = web.get("/api/agent").json()
    assert s["state"] == "consent" and s["consent"]["name"] == name, s
    out = web.post("/api/agent/allow").json()
    assert out["state"] == "active" and out["agent"]["kind"] == "mcp" and out["agent"]["name"] == name, out
    return token


def test_pairing_shows_the_connector_and_a_reload_keeps_it(kitchens):
    demo, _, _, a, _ = kitchens
    token = start_pairing(demo)
    assert demo.get("/api/agent").json()["pairing"]["mcpUrl"] == f"http://testserver/mcp/c/{token}/"
    assert connect.connector_ctx(token).account["id"] == a
    assert demo.get("/api/agent").json()["state"] == "pairing"  # looking it up is no request on the URL


def test_a_pairing_from_before_connector_urls_gets_one(kitchens):
    demo, _, agent, a, _ = kitchens
    start_pairing(demo)
    connect.drop_connector(get_accounts().ctx(a))  # as a pairing started before the deploy left it
    m = URL.fullmatch(demo.get("/api/agent").json()["pairing"]["mcpUrl"])
    assert m, "an old pairing must still show the connector URL"
    Mcp(agent, f"/mcp/c/{m.group(1)}/")
    assert demo.get("/api/agent").json()["state"] == "consent"


def test_tools_wait_for_allow(kitchens):
    demo, _, agent, _, _ = kitchens
    token = start_pairing(demo)
    m = Mcp(agent, f"/mcp/c/{token}/")
    assert demo.get("/api/agent").json()["state"] == "consent"
    res = m.call("request_supply", {"lines": MILK})
    code = demo.get("/api/agent").json()["consent"]["verifyCode"]
    assert res.get("isError") and res["content"][0]["text"].startswith(
        f"Waiting for the kitchen to press Allow in Validio. Show the user this verification code: {code}. "
        "It must match the code on the Validio Agent page.")
    assert demo.get("/api/inbox").json() == []


def test_token_is_kept_as_a_hash_after_allow_and_ends_on_disconnect(kitchens):
    demo, _, agent, a, _ = kitchens
    token = connect_app(demo, agent)
    s = demo.get("/api/agent").json()
    assert s["agent"]["kind"] == "mcp" and "pairing" not in s
    db, _ = get_accounts().paths(a)
    con = sqlite3.connect(db)
    stored, clear = con.execute("select token_hash, token from connector").fetchone()
    con.close()
    assert stored == hashlib.sha256(token.encode()).hexdigest() and clear is None
    assert token.encode() not in db.read_bytes()
    assert connect.connector_ctx(token).account["id"] == a
    assert connect.connector_ctx(token[:-1] + ("A" if token[-1] != "A" else "B")) is None
    demo.post("/api/agent/disconnect")
    assert connect.connector_ctx(token) is None
    again = connect_app(demo, agent)  # a new pairing makes a new token, the old one stays dead
    assert again != token and connect.connector_ctx(token) is None and connect.connector_ctx(again) is not None


def test_cancel_and_a_new_pairing_end_the_token(kitchens):
    demo, _, _, _, _ = kitchens
    token = start_pairing(demo)
    second = start_pairing(demo)
    assert connect.connector_ctx(token) is None and connect.connector_ctx(second) is not None
    demo.post("/api/agent/deny")
    assert connect.connector_ctx(second) is None


def test_the_url_outlives_the_code(kitchens, monkeypatch):
    from datetime import timedelta

    demo, _, agent, _, _ = kitchens
    token = start_pairing(demo)
    later = connect._wall() + timedelta(hours=2)
    monkeypatch.setattr(connect, "_wall", lambda: later)
    Mcp(agent, f"/mcp/c/{token}/")
    assert demo.get("/api/agent").json()["state"] == "consent"


def test_an_agent_with_its_own_key_ends_the_connector(kitchens):
    demo, _, _, a, _ = kitchens
    token = start_pairing(demo)
    demo.post("/api/agent/deny")
    pair_demo_agent(get_accounts().ctx(a))
    out = demo.post("/api/agent/allow").json()
    assert out["agent"]["kind"] == "agent" and connect.connector_ctx(token) is None


def test_the_code_still_pairs_a_signing_agent(kitchens):
    demo, _, _, a, _ = kitchens
    token = start_pairing(demo)
    pair_demo_agent(get_accounts().ctx(a))  # a signing agent answers the code on /agent/v1/pair
    assert demo.get("/api/agent").json()["consent"]["name"] != "MCP agent"
    demo.post("/api/agent/allow")
    assert connect.connector_ctx(token) is None


def test_orders_alone_without_any_pass(kitchens):
    demo, _, agent, _, _ = kitchens
    m = Mcp(agent, f"/mcp/c/{connect_app(demo, agent)}/", name=AGENT)
    res = m.call("request_supply", {"lines": MILK, "deliverBy": "2026-11-16"})
    assert not res.get("isError"), res
    req = res["structuredContent"]
    assert req["decision"]["outcome"] == "auto_order", req["decision"]
    choice = [{"productId": ln["chosen"]["productId"], "salesQty": ln["chosen"]["salesQty"]} for ln in req["lines"]]
    order = m.call("confirm_order", {"requestId": req["id"], "choice": choice})
    assert not order.get("isError"), order
    inbox = {i["id"]: i for i in demo.get("/api/inbox").json()}
    assert inbox[req["id"]]["status"] == "ordered_alone"
    assert m.call("get_request", {"requestId": req["id"]})["structuredContent"]["status"] == "ordered_alone"
    # no idempotencyKey: the same words again are a new request, not the old one handed back
    second = m.call("request_supply", {"lines": MILK, "deliverBy": "2026-11-16"})["structuredContent"]
    assert second["id"] != req["id"]
    actors = {e.get("actorText") for e in demo.get("/api/ledger").json()["entries"]}
    assert AGENT in actors


def test_waits_for_the_kitchens_approval(kitchens):
    demo, _, agent, _, _ = kitchens
    m = Mcp(agent, f"/mcp/c/{connect_app(demo, agent)}/", name=AGENT)
    big = [{"text": "1500 litres of lactose-free milk"}]  # above what the demo Rules let it order alone
    req = m.call("request_supply", {"lines": big, "deliverBy": "2026-11-16"})["structuredContent"]
    assert req["decision"]["outcome"] == "ask_human" and req["orderId"], req["decision"]
    order = m.call("get_order", {"orderId": req["orderId"]})["structuredContent"]
    assert order["state"] == "waiting"


def test_refused_while_paused_with_a_ledger_entry(kitchens):
    demo, _, agent, _, _ = kitchens
    m = Mcp(agent, f"/mcp/c/{connect_app(demo, agent)}/", name=AGENT)
    demo.post("/api/agent/pause", json={"paused": True})
    res = m.call("request_supply", {"lines": MILK, "deliverBy": "2026-11-16"})
    assert res.get("isError") and "paused" in res["content"][0]["text"]
    refused = [e for e in demo.get("/api/ledger").json()["entries"] if e["sentence"].startswith(f"Refused {AGENT}")]
    assert len(refused) == 1


def test_404_after_disconnect_and_for_unknown_tokens(kitchens):
    demo, _, agent, _, _ = kitchens
    token = connect_app(demo, agent)
    assert agent.post(f"/mcp/c/{token}/", headers=MCP_HEADERS, json=_init(1)).status_code == 200
    demo.post("/api/agent/disconnect")
    assert agent.post(f"/mcp/c/{token}/", headers=MCP_HEADERS, json=_init(1)).status_code == 404
    assert agent.post("/mcp/c/not-a-token/", headers=MCP_HEADERS, json=_init(1)).status_code == 404


def test_the_kitchen_path_still_needs_the_pass(kitchens):
    demo, _, agent, a, _ = kitchens
    connect_app(demo, agent)
    m = Mcp(agent, f"/mcp/k/{a}/")
    res = m.call("request_supply", {"lines": MILK, "idempotencyKey": "k1", "deliverBy": "2026-11-16"})
    assert res.get("isError"), res


def test_a_public_host_is_allowed_on_the_connector(app_env, monkeypatch):  # noqa: F811
    monkeypatch.setenv("VALIDIO_MCP_HOSTS", "kitchen.example.org")
    pub = TestClient(app_env, base_url="https://kitchen.example.org")
    evil = TestClient(app_env, base_url="https://evil.example.org")
    with TestClient(app_env) as demo, pub, evil:
        demo.post("/api/account/demo")
        token = connect_app(demo, pub)
        assert pub.post(f"/mcp/c/{token}/", headers=MCP_HEADERS, json=_init(1)).status_code == 200
        assert evil.post(f"/mcp/c/{token}/", headers=MCP_HEADERS, json=_init(1)).status_code == 421


# the way any MCP agent does it: the python mcp Client with only the URL, over streamable HTTP, against a
# running server


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def _first_call(url: str) -> str:
    from mcp import Client

    async with Client(url) as c:
        r = await c.call_tool("request_supply", {"lines": MILK})
        return " ".join(getattr(x, "text", "") for x in r.content) if r.is_error else "no error"


@contextlib.contextmanager
def _serve(app):
    """The app on a free port of this machine, as a deployed server answers."""
    import uvicorn

    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    try:
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.05)
        yield port
    finally:
        server.should_exit = True
        t.join(5)


WAIT_TEXT = re.compile(r"Waiting for the kitchen to press Allow in Validio\. Show the user this verification code: "
                       r"([A-Z2-9]{3}-[A-Z2-9]{3})\. It must match the code on the Validio Agent page\.")


def test_mcp_client_with_only_the_url_orders_after_allow(app_env):  # noqa: F811
    import httpx

    spec = importlib.util.spec_from_file_location("connector_check", ROOT / "scripts" / "connector_check.py")
    check = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(check)
    with _serve(app_env) as port, httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=60) as web:
        web.post("/api/account/demo")
        url = web.post("/api/agent/pair").json()["pairing"]["mcpUrl"]
        assert re.fullmatch(rf"http://127\.0\.0\.1:{port}/mcp/c/[A-Za-z0-9_-]{{43}}/", url), url
        lines: list[str] = []
        waiting = asyncio.run(check.order_milk(url, say=lines.append))
        s = web.get("/api/agent").json()
        assert waiting["verifyCode"] == s["consent"]["verifyCode"]
        assert f"verification code: {s['consent']['verifyCode']} (must match the code on the Validio Agent page)" in lines
        assert s["state"] == "consent" and s["consent"]["name"] == "mcp"  # the python mcp Client's own name
        assert web.post("/api/agent/allow").json()["state"] == "active"
        lines: list[str] = []
        out = asyncio.run(check.order_milk(url, say=lines.append))
        assert out["status"] == "ordered_alone", lines
        assert out["request"]["id"] in {i["id"] for i in web.get("/api/inbox").json()}


def test_the_agent_shows_the_verification_code_of_the_agent_page(app_env):  # noqa: F811
    """The python mcp Client gets the code in the tool error; the Agent page shows the same one. A new
    connection gets a new code; Allow clears it."""
    import httpx

    with _serve(app_env) as port, httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=60) as web:
        web.post("/api/account/demo")
        url = web.post("/api/agent/pair").json()["pairing"]["mcpUrl"]
        said = asyncio.run(_first_call(url))
        m = WAIT_TEXT.match(said)
        assert m, said
        consent = web.get("/api/agent").json()["consent"]
        assert consent["verifyCode"] == m.group(1)
        assert not set(m.group(1)) & set("0O1IL")
        assert WAIT_TEXT.match(asyncio.run(_first_call(url))).group(1) == m.group(1)  # stable while it waits
        assert consent["at"] and web.get("/api/agent").json()["consent"]["at"] == consent["at"]  # the first call's time

        web.post("/api/agent/deny")
        again = web.post("/api/agent/pair").json()["pairing"]["mcpUrl"]
        second = WAIT_TEXT.match(asyncio.run(_first_call(again)))
        assert second and second.group(1) != m.group(1)
        assert web.get("/api/agent").json()["consent"]["verifyCode"] == second.group(1)

        s = web.post("/api/agent/allow").json()
        assert s["state"] == "active" and "consent" not in s
        db, _ = get_accounts().paths(web.get("/api/account").json()["id"])
        con = sqlite3.connect(db)
        assert con.execute("select verify_code from agent_link").fetchone() == (None,)
        con.close()


# the agent's name: what the MCP client says in clientInfo on its first request, "MCP agent" without one


async def _order_as(url: str, name: str) -> dict:
    from mcp import Client
    from mcp.types import Implementation

    async with Client(url, client_info=Implementation(name=name, version="2.1.0")) as c:
        r = await c.call_tool("request_supply", {"lines": MILK, "deliverBy": "2026-11-16"})
        if r.is_error:
            return {"error": " ".join(getattr(x, "text", "") for x in r.content)}
        req = r.structured_content or json.loads("".join(getattr(x, "text", "") for x in r.content))
        req = req.get("result", req) if set(req) == {"result"} else req
        choice = [{"productId": ln["chosen"]["productId"], "salesQty": ln["chosen"]["salesQty"]} for ln in req["lines"]]
        await c.call_tool("confirm_order", {"requestId": req["id"], "choice": choice})
        return req


def test_a_real_mcp_client_shows_up_under_its_own_name(app_env):  # noqa: F811
    """The python mcp Client over streamable HTTP against a running server, as Claude Code connects: its
    clientInfo.name is the name on the consent screen, the Agent page, the ledger, Home and Activity."""
    import httpx

    with _serve(app_env) as port, httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=60) as web:
        web.post("/api/account/demo")
        url = web.post("/api/agent/pair").json()["pairing"]["mcpUrl"]
        waiting = asyncio.run(_order_as(url, "Claude Code"))
        assert WAIT_TEXT.match(waiting["error"]), waiting
        s = web.get("/api/agent").json()
        assert s["state"] == "consent" and s["consent"]["name"] == "Claude Code", s
        assert web.get("/api/home").json()["agent"] == {"state": "consent", "name": "Claude Code", "lastUsedAt": None}
        s = web.post("/api/agent/allow").json()
        assert s["agent"]["name"] == "Claude Code" and s["agent"]["kind"] == "mcp"

        req = asyncio.run(_order_as(url, "Claude Code"))
        assert req.get("decision", {}).get("outcome") == "auto_order", req
        ledger = web.get("/api/ledger").json()["entries"]
        asked = [e for e in ledger if e["kind"] == "request"]
        assert asked and asked[-1]["actorText"] == "Claude Code" and asked[-1]["actor"] == "agent:claude-code"
        assert any(e["sentence"].startswith("Connected Claude Code. Spend Pass M-1 is now version")
                   for e in ledger), [e["sentence"] for e in ledger if e["kind"] == "agent"]
        d = web.get(f"/api/activity/{req['id']}").json()
        assert d["asked"]["agentName"] == "Claude Code" and d["proof"][0]["actor"] == "Claude Code"
        assert d["item"]["status"] == "ordered"
        home = web.get("/api/home").json()
        assert home["agent"]["name"] == "Claude Code" and home["agent"]["state"] == "active"


def _consent_name(web, agent, init: dict) -> str:
    token = start_pairing(web)
    assert agent.post(f"/mcp/c/{token}/", headers=MCP_HEADERS, json=init).status_code == 200
    name = web.get("/api/agent").json()["consent"]["name"]
    web.post("/api/agent/deny")
    return name


def _init_with(info) -> dict:
    out = _init(1)
    if info is None:
        out["params"].pop("clientInfo")
    else:
        out["params"]["clientInfo"] = info
    return out


@pytest.mark.parametrize(("info", "want"), [
    ({"name": "Cursor", "version": "1"}, "Cursor"),
    ({"name": "claude-code", "version": "1"}, "Claude Code"),  # the id some clients send as their name
    ({"name": "my-bot", "title": "Kitchen Buyer", "version": "1"}, "Kitchen Buyer"),  # the title wins
    ({"name": "  Two \n lines\t", "version": "1"}, "Two lines"),
    ({"name": "x" * 200, "version": "1"}, "x" * 60),
    ({"name": "", "version": "1"}, "MCP agent"),
    ({"name": "Validio", "version": "1"}, "MCP agent"),  # never a name the screens give someone else
    ({"name": 42, "version": "1"}, "MCP agent"),
    (None, "MCP agent"),
])
def test_the_consent_takes_the_client_name(kitchens, info, want):
    demo, _, agent, _, _ = kitchens
    assert _consent_name(demo, agent, _init_with(info)) == want


def test_a_first_request_without_a_name_is_named_by_the_initialize_after_it(kitchens):
    demo, _, agent, _, _ = kitchens
    token = start_pairing(demo)
    agent.get(f"/mcp/c/{token}/", headers=MCP_HEADERS)  # no body, no name
    assert demo.get("/api/agent").json()["consent"]["name"] == "MCP agent"
    Mcp(agent, f"/mcp/c/{token}/", name="Cursor")
    assert demo.get("/api/agent").json()["consent"]["name"] == "Cursor"
    Mcp(agent, f"/mcp/c/{token}/", name="Someone Else")  # a name once given stays
    assert demo.get("/api/agent").json()["consent"]["name"] == "Cursor"
    demo.post("/api/agent/allow")
    Mcp(agent, f"/mcp/c/{token}/", name="Renamed")
    assert demo.get("/api/agent").json()["agent"]["name"] == "Cursor"


def test_the_body_reaches_the_mcp_server_unchanged(kitchens):
    """Reading the name must not eat the request: a big initialize still answers."""
    demo, _, agent, _, _ = kitchens
    token = start_pairing(demo)
    init = _init(1, "Big")
    init["params"]["capabilities"] = {"experimental": {"pad": {"x": "y" * 300_000}}}
    r = agent.post(f"/mcp/c/{token}/", headers=MCP_HEADERS, json=init)
    assert r.status_code == 200 and "serverInfo" in r.text
    assert demo.get("/api/agent").json()["consent"]["name"] == "Big"
