"""B3: the account in the agent URLs. /agent/v1/k/{account}/... and /mcp/k/{account}/ work on that kitchen's
store; the old /agent/v1 and /mcp/ stay on the local kitchen."""

import json

import pytest
from fastapi.testclient import TestClient
from test_accounts import SIGNUP, app_env, ask_as_agent, connect_demo_agent  # noqa: F401

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
    h = holder(agent, a)
    pa = {"Authorization": f"SD-JWT {h.presentation()}"}
    assert agent.get(f"/agent/v1/k/{a}/requests/{rid}", headers=pa).json()["id"] == rid
    assert agent.get(f"/agent/v1/k/{b}/requests/{rid}").status_code == 401


def test_a_pass_from_one_kitchen_is_refused_in_another(kitchens):
    _, _, agent, a, b = kitchens
    h = holder(agent, a)
    h.nonce = lambda: agent.get(f"/agent/v1/k/{b}/nonce").json()
    r = ask(agent, b, h)
    assert r.status_code == 401


@pytest.mark.parametrize("account", ["k-00000000", "k-" + "0" * 32, "k-ZZZZZZZZ", "k-zz"])
def test_an_unknown_kitchen_is_404(kitchens, account):
    _, _, agent, *_ = kitchens
    assert agent.get(f"/agent/v1/k/{account}/nonce").status_code == 404
    assert agent.post(f"/mcp/k/{account}/", headers=MCP_HEADERS, json=_init(1)).status_code == 404


def test_pairing_through_the_kitchen_path(kitchens):
    import re

    from jwcrypto.jwk import JWK

    _, two, agent, _, b = kitchens
    s = two.post("/api/agent/pair").json()
    assert re.fullmatch(r"http://testserver/mcp/c/[A-Za-z0-9_-]{43}/", s["pairing"]["mcpUrl"])  # any MCP agent
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


def _init(i, name="test"):
    return {"jsonrpc": "2.0", "id": i, "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                       "clientInfo": {"name": name, "version": "1"}}}


def _answer(r) -> dict:
    assert r.status_code == 200, r.text
    if r.headers["content-type"].startswith("text/event-stream"):
        data = [ln[5:].strip() for ln in r.text.splitlines() if ln.startswith("data:")]
        return json.loads(data[-1])
    return r.json()


class Mcp:
    def __init__(self, http, path, name="test"):
        self.http, self.path, self.n = http, path, 1
        r = http.post(path, headers=MCP_HEADERS, json=_init(1, name))
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
    assert m.call("get_request", {"requestId": rid, "spendPass": h.presentation()})["structuredContent"]["id"] == rid
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


def test_an_in_process_agent_runs_on_the_account(kitchens):
    one, two, *_ = kitchens
    rid = ask_as_agent(one)
    assert rid
    assert [i["id"] for i in one.get("/api/inbox").json()] == [rid]
    assert two.get("/api/inbox").json() == []


# reads need the kitchen's pass on the per-kitchen routes (account ids alone are no secret)


def _placed(agent, a):
    h = holder(agent, a)
    r = ask(agent, a, h, "read-1")
    assert r.status_code == 200, r.text
    return h, r.json()["id"]


def test_account_ids_carry_128_random_bits(kitchens):
    import re

    *_, a, b = kitchens
    assert re.fullmatch(r"k-[0-9a-f]{32}", a) and re.fullmatch(r"k-[0-9a-f]{32}", b)


def test_http_reads_need_the_kitchens_pass(kitchens):
    _, _, agent, a, _ = kitchens
    h, rid = _placed(agent, a)
    r = agent.get(f"/agent/v1/k/{a}/requests/{rid}")
    assert r.status_code == 401 and rid not in r.text
    r = agent.get(f"/agent/v1/k/{a}/requests/{rid}", headers={"Authorization": "SD-JWT not-a-pass"})
    assert r.status_code == 401 and rid not in r.text
    ok = agent.get(f"/agent/v1/k/{a}/requests/{rid}", headers={"Authorization": f"SD-JWT {h.presentation()}"})
    assert ok.status_code == 200 and ok.json()["id"] == rid
    oid = ok.json().get("orderId")
    if oid:
        assert agent.get(f"/agent/v1/k/{a}/orders/{oid}").status_code == 401
        r = agent.get(f"/agent/v1/k/{a}/orders/{oid}", headers={"Authorization": f"SD-JWT {h.presentation()}"})
        assert r.status_code == 200


def test_a_pass_of_another_demo_copy_reads_nothing(kitchens, app_env, tmp_path):  # noqa: F811
    """Demo copies share the template's kitchen key and demo agent key, so a pass from copy C must still be
    refused in copy D."""
    from validio.demo import seed

    _, _, agent, *_ = kitchens
    seed.reset(tmp_path / "template" / "validio.db", tmp_path / "template" / "keys")
    with TestClient(app_env) as three, TestClient(app_env) as four:
        c = three.post("/api/account/demo").json()["id"]
        d = four.post("/api/account/demo").json()["id"]
        connect_demo_agent(three)
        connect_demo_agent(four)
        assert (get_accounts().paths(c)[1] / "kitchen-es256.json").read_text() == \
            (get_accounts().paths(d)[1] / "kitchen-es256.json").read_text()  # the shared key
        r = ask(agent, d, holder(agent, d), "d-1")
        assert r.status_code == 200
        rid = r.json()["id"]
        hc = holder(agent, c)
        hc.nonce = lambda: agent.get(f"/agent/v1/k/{d}/nonce").json()
        r = agent.get(f"/agent/v1/k/{d}/requests/{rid}", headers={"Authorization": f"SD-JWT {hc.presentation()}"})
        assert r.status_code == 401 and rid not in r.text
        assert ask(agent, d, hc, "c-in-d").status_code == 401  # nor write
        assert three.get("/api/inbox").json() == []


def test_mcp_reads_need_the_kitchens_pass(kitchens):
    _, _, agent, a, b = kitchens
    m = Mcp(agent, f"/mcp/k/{a}/")
    h = holder(agent, a)
    h.nonce = lambda: m.read(f"validio://k/{a}/nonce")
    res = m.call("request_supply", {"spendPass": h.presentation(), "lines": MILK, "idempotencyKey": "m2",
                                    "deliverBy": "2026-11-16"})
    rid = res["structuredContent"]["id"]
    bare = m.call("get_request", {"requestId": rid})
    assert bare.get("isError") and "401" in bare["content"][0]["text"] and rid not in json.dumps(bare)
    bad = m.call("get_request", {"requestId": rid, "spendPass": "not-a-pass"})
    assert bad.get("isError") and "401" in bad["content"][0]["text"]
    good = m.call("get_request", {"requestId": rid, "spendPass": h.presentation()})
    assert good["structuredContent"]["id"] == rid
    other = Mcp(agent, f"/mcp/k/{b}/")
    hb = holder(agent, a)
    hb.nonce = lambda: other.read(f"validio://k/{b}/nonce")
    leak = other.call("get_request", {"requestId": rid, "spendPass": hb.presentation()})
    assert leak.get("isError") and rid not in json.dumps(leak)
