"""Scene 4 for the kitchen's agent: it renews the Steady Order through the MCP tool renew_steady_order
(lane D's POST /api/steady/{id}/renew behind it) and prints what was ordered and what waits for the chef."""

import io
import json

import pytest
from mcp import Client

from validio.agent.buyer import run_scene
from validio.agent.holder import Holder
from validio.agent.llm import FakeLLM
from validio.agent.pane import printer
from validio.agent.port import McpPort
from validio.api import tools
from validio.api.mcp_server import server


async def pane(ctx):
    h = Holder.from_seed(lambda: tools.nonce(ctx), ctx.db_path, ctx.keys_dir)
    out, llm = io.StringIO(), FakeLLM(4)
    async with McpPort(server, spend_pass=h.presentation) as port:
        t = await run_scene(4, llm, port, on_event=printer(color=False, out=out))
    return out.getvalue(), t, llm


@pytest.mark.asyncio
async def test_renew_needs_the_spend_pass(ctx):
    async with Client(server) as c:
        r = await c.call_tool("renew_steady_order", {"spendPass": "not-a-pass", "orderId": "S-1"})
    assert r.is_error and "401" in r.content[0].text


@pytest.mark.asyncio
async def test_renew_unknown_order_is_404(ctx):
    h = Holder.from_seed(lambda: tools.nonce(ctx), ctx.db_path, ctx.keys_dir)
    async with McpPort(server, spend_pass=h.presentation) as port:
        a = await port.call("renew_steady_order", {"orderId": "S-9"})
    assert "404" in a["error"]


@pytest.mark.asyncio
async def test_pane_scene4_renews_and_names_what_waits(ctx):
    text, t, llm = await pane(ctx)
    assert [e.name for e in t.events if e.kind == "call"] == ["renew_steady_order"]
    assert "renewed        464306" in text and "split_renewed  463968" in text
    assert "waits for the chef:" in text
    assert "471376" in text and "Order 27 now" in text
    assert "466375" in text and "Renew anyway" in text
    assert t.final == ("Steady Order S-1 is renewed: 464306 and 463968 are ordered alone, "
                       "471376 and 466375 wait for the chef.")
    assert "untrusted" not in json.dumps(llm.inputs).lower()


@pytest.mark.asyncio
async def test_scene4_twice_orders_nothing_twice(ctx):
    _, first, _ = await pane(ctx)
    _, second, _ = await pane(ctx)
    ids = [[ln.get("orderId") for ln in t.events[2].data["lines"]] for t in (first, second)]
    assert ids[0] == ids[1] and ids[0][0]
