"""B3: the account in the agent URLs. /agent/v1/k/{account}/... and /mcp/k/{account}/ work on that kitchen's
store; the old /agent/v1 and /mcp/ stay on the local kitchen."""

import json

import pytest
from fastapi.testclient import TestClient
from test_accounts import SIGNUP, app_env, connect_demo_agent  # noqa: F401

from validio.agent.holder import Holder
from validio.api.accounts import get_accounts

MILK = [{"text": "1000 litres of lactose-free milk by Monday"}]
MCP_HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


@pytest.fixture
def kitchens(app_env):  # noqa: F811
    """A demo copy with the demo agent connected, a signed-up kitchen, and an agent client for each."""
    agent_http = TestClient(app_env, base_url="http://127.0.0.1:8410")  # MCP checks the Host header
    with TestClient(app_env) as one, TestClient(app_env) as two, agent_http as agent:
        a = one.post("/api/account/demo").json()["id"]
        connect_demo_agent(one)
        b = two.post("/api/account/signup", json=SIGNUP).json()["id"]
        yield one, two, agent, a, b


def holder(agent, account):
    db, keys = get_accounts().paths(account)
    return Holder.from_seed(lambda: agent.get(f"/agent/v1/k/{account}/nonce").json(), db, keys)


def ask(agent, account, h, key="k1"):
    return agent.post(f"/agent/v1/k/{account}/requests", headers={"Authorization": f"SD-JWT {h.presentation()}"},
                      json={"lines": MILK, "deliverBy": "2026-11-16", "idempotencyKey": key})


def test_agent_http_works_on_the_kitchen_in_the_path(kitchens, ctx):
    one, two, agent, a, b = kitchens
    local_before = len(ctx.audit.list())
    r = ask(agent, a, holder(agent, a))
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    assert [i["id"] for i in one.get("/api/inbox").json()] == [rid]
    assert two.get("/api/inbox").json() == []
    assert len(ctx.audit.list()) == local_before
    assert agent.get(f"/agent/v1/k/{a}/requests/{rid}").json()["id"] == rid
    assert agent.get(f"/agent/v1/k/{b}/requests/{rid}").status_code == 404


def test_a_pass_from_one_kitchen_is_refused_in_another(kitchens):
    _, _, agent, a, b = kitchens
    h = holder(agent, a)
    h.nonce = lambda: agent.get(f"/agent/v1/k/{b}/nonce").json()
    r = ask(agent, b, h)
    assert r.status_code == 401


@pytest.mark.parametrize("account", ["k-00000000", "k-ZZZZZZZZ", "k-zz"])
def test_an_unknown_kitchen_is_404(kitchens, account):
    _, _, agent, *_ = kitchens
    assert agent.get(f"/agent/v1/k/{account}/nonce").status_code == 404
    assert agent.post(f"/mcp/k/{account}/", headers=MCP_HEADERS, json=_init(1)).status_code == 404


def test_pairing_through_the_kitchen_path(kitchens):
    from jwcrypto.jwk import JWK

    _, two, agent, _, b = kitchens
    s = two.post("/api/agent/pair").json()
    assert s["pairing"]["mcpUrl"] == f"http://testserver/mcp/k/{b}/"
    assert s["pairing"]["apiUrl"] == f"http://testserver/agent/v1/k/{b}"
    key = JWK.generate(kty="EC", crv="P-256")
    r = agent.post(f"/agent/v1/k/{b}/pair", json={"code": s["pairing"]["code"], "name": "Buyer B",
                                                  "publicJwk": key.export_public(as_dict=True)})
    assert r.status_code == 202, r.text
    assert two.get("/api/agent").json()["consent"]["name"] == "Buyer B"
    two.post("/api/agent/allow")
    got = agent.get(f"/agent/v1/k/{b}/pass", params={"code": s["pairing"]["code"]}).json()
    mine = Holder(got["spendPass"], key, lambda: agent.get(f"/agent/v1/k/{b}/nonce").json())
    assert ask(agent, b, mine).status_code == 200


# MCP over streamable HTTP, raw JSON-RPC


def _init(i):
    return {"jsonrpc": "2.0", "id": i, "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                       "clientInfo": {"name": "test", "version": "1"}}}


def _answer(r) -> dict:
    assert r.status_code == 200, r.text
    if r.headers["content-type"].startswith("text/event-stream"):
        data = [ln[5:].strip() for ln in r.text.splitlines() if ln.startswith("data:")]
        return json.loads(data[-1])
    return r.json()


class Mcp:
    def __init__(self, http, path):
        self.http, self.path, self.n = http, path, 1
        r = http.post(path, headers=MCP_HEADERS, json=_init(1))
        _answer(r)
        self.headers = {**MCP_HEADERS, "mcp-session-id": r.headers.get("mcp-session-id", ""),
                        "mcp-protocol-version": "2025-06-18"}
        http.post(path, headers=self.headers, json={"jsonrpc": "2.0", "method": "notifications/initialized"})

    def call(self, name, args):
        self.n += 1
        out = _answer(self.http.post(self.path, headers=self.headers, json={
            "jsonrpc": "2.0", "id": self.n, "method": "tools/call", "params": {"name": name, "arguments": args}}))
        res = out["result"]
        if not res.get("isError") and "structuredContent" not in res:
            res["structuredContent"] = json.loads(res["content"][0]["text"])
        return res

    def read(self, uri):
        self.n += 1
        out = _answer(self.http.post(self.path, headers=self.headers, json={
            "jsonrpc": "2.0", "id": self.n, "method": "resources/read", "params": {"uri": uri}}))
        return json.loads(out["result"]["contents"][0]["text"])


def test_mcp_works_on_the_kitchen_in_the_path(kitchens, ctx):
    one, two, agent, a, b = kitchens
    local_before = len(ctx.audit.list())
    m = Mcp(agent, f"/mcp/k/{a}/")
    h = holder(agent, a)
    h.nonce = lambda: m.read(f"validio://k/{a}/nonce")
    res = m.call("request_supply", {"spendPass": h.presentation(), "lines": MILK, "idempotencyKey": "m1",
                                    "deliverBy": "2026-11-16"})
    assert not res.get("isError"), res
    rid = res["structuredContent"]["id"]
    assert [i["id"] for i in one.get("/api/inbox").json()] == [rid]
    assert len(ctx.audit.list()) == local_before
    assert m.call("get_request", {"requestId": rid})["structuredContent"]["id"] == rid
    other = Mcp(agent, f"/mcp/k/{b}/")
    assert other.call("get_request", {"requestId": rid}).get("isError")
    assert two.get("/api/inbox").json() == []


def test_mcp_without_a_kitchen_stays_local(kitchens, ctx):
    _, _, agent, _, _ = kitchens
    m = Mcp(agent, "/mcp/")
    h = Holder.from_seed(lambda: m.read("validio://nonce"), ctx.db_path, ctx.keys_dir)
    res = m.call("request_supply", {"spendPass": h.presentation(), "lines": MILK, "idempotencyKey": "l1",
                                    "deliverBy": "2026-11-16"})
    assert not res.get("isError"), res
    assert ctx.store.requests()[-1]["id"] == res["structuredContent"]["id"]


def test_example_request_runs_on_the_account(kitchens):
    one, two, *_ = kitchens
    r = one.post("/api/demo/example")
    assert r.status_code == 200, r.text
    rid = r.json()["requestId"]
    assert [i["id"] for i in one.get("/api/inbox").json()] == [rid]
    assert two.get("/api/inbox").json() == []
