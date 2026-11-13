"""Step 10, MCP: the same five tools as /agent/v1, the same code path. Scene 2 end to end with the
purchasing agent's fixed twin over an in-process MCP client."""

import json

import pytest
from mcp import Client

from validio.agent.buyer import run_scene
from validio.agent.holder import Holder
from validio.agent.llm import FakeLLM
from validio.agent.port import McpPort
from validio.api import tools
from validio.api.mcp_server import server

FIVE = {"search_products", "request_supply", "get_request", "confirm_order", "get_order"}


def holder_for(ctx):
    return Holder.from_seed(lambda: tools.nonce(ctx).nonce, ctx.db_path, ctx.keys_dir)


@pytest.mark.asyncio
async def test_mcp_lists_five_tools(ctx):
    async with Client(server) as c:
        assert {t.name for t in (await c.list_tools()).tools} == FIVE


@pytest.mark.asyncio
async def test_scene2_end_to_end_mcp(ctx):
    h = holder_for(ctx)
    async with McpPort(server, spend_pass=h.presentation) as port:
        t = await run_scene(2, FakeLLM(2), port)
    calls = [(e.name, e.data) for e in t.events if e.kind == "call"]
    assert [n for n, _ in calls] == ["request_supply", "confirm_order", "get_order"]
    order = next(e.data for e in reversed(t.events) if e.kind == "answer" and e.name == "get_order")
    assert order["state"] == "placed" and order["totalCents"] == 101000
    assert [(ln["productId"], ln["quantity"]) for ln in order["lines"]] == [("464306", 1000)]
    assert t.final.endswith("is placed.")
    assert ctx.audit.verify().ok


@pytest.mark.asyncio
async def test_mcp_and_http_give_the_same_result(ctx):
    from fastapi.testclient import TestClient

    from validio.api.app import app

    h = holder_for(ctx)
    line = [{"text": "1000 litres of lactose-free milk by Monday"}]
    async with Client(server) as c:
        r = await c.call_tool("request_supply", {"spendPass": h.presentation(), "lines": line,
                                                 "idempotencyKey": "mcp-1", "deliverBy": "2026-11-16"})
    assert not r.is_error, r.content
    via_mcp = r.structured_content or json.loads(r.content[0].text)
    with TestClient(app) as client:
        via_http = client.post("/agent/v1/requests", headers={"Authorization": f"SD-JWT {h.presentation()}"},
                               json={"lines": line, "idempotencyKey": "http-1", "deliverBy": "2026-11-16"}).json()
    for k in ("decision", "liveChecked", "status"):
        assert via_mcp[k] == via_http[k]
    assert via_mcp["lines"][0]["chosen"] == via_http["lines"][0]["chosen"]


@pytest.mark.asyncio
async def test_mcp_refuses_tampered_and_reused_pass(ctx):
    h = holder_for(ctx)
    token = h.presentation()
    args = {"lines": [{"text": "10 litres of lactose-free milk by Monday"}], "idempotencyKey": "t"}
    async with Client(server) as c:
        bad = token[:20] + ("A" if token[20] != "A" else "B") + token[21:]
        r = await c.call_tool("request_supply", {**args, "spendPass": bad})
        assert r.is_error
        assert not (await c.call_tool("request_supply", {**args, "spendPass": token})).is_error
        r = await c.call_tool("request_supply", {**args, "idempotencyKey": "t2", "spendPass": token})
        assert r.is_error and "nonce" in " ".join(getattr(x, "text", "") for x in r.content)


@pytest.mark.asyncio
async def test_search_products_mcp_no_live_call(ctx):
    async with Client(server) as c:
        r = await c.call_tool("search_products", {"text": "lactose free milk", "limit": 5})
    hits = r.structured_content["result"] if r.structured_content else json.loads(r.content[0].text)
    assert 0 < len(hits) <= 5
    assert ctx.valio.calls == 0
