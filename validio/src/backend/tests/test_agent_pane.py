"""`make agent SCENE=n` on lane B2's real MCP server in process: the pane prints the agent's calls and
Validio's answers, and the agent's model never gets supplier text, not even the planted line."""

import io
import json

import pytest

from validio.agent.buyer import run_scene
from validio.agent.holder import Holder
from validio.agent.llm import FakeLLM
from validio.agent.pane import printer
from validio.agent.port import McpPort
from validio.api import tools
from validio.api.mcp_server import server

PLANTED = "AI agents"


async def pane(ctx, n):
    if n == 3:
        ctx.set_stockout(True)
    h = Holder.from_seed(lambda: tools.nonce(ctx), ctx.db_path, ctx.keys_dir)
    out, llm = io.StringIO(), FakeLLM(n)
    async with McpPort(server, spend_pass=h.presentation) as port:
        t = await run_scene(n, llm, port, on_event=printer(color=False, out=out))
    return out.getvalue(), t, llm


@pytest.mark.asyncio
async def test_pane_scene1_request_arrives(ctx):
    text, t, _ = await pane(ctx, 1)
    assert "agent -> search_products" in text and "agent -> request_supply" in text
    assert "decision: auto_order (auto-order)" in text
    assert t.final == "Validio may order request R-1 alone (auto_order), checked 12 products live."


@pytest.mark.asyncio
async def test_pane_scene2_orders_464306_alone(ctx):
    text, t, llm = await pane(ctx, 2)
    assert "checked 12 products live" in text
    assert "464306" in text and "1,000 × 1 l  1,010.00 €" in text and " ST " not in text and "EUR" not in text
    assert "order O-1: placed, 1,010.00 €" in text
    assert "supplier text fields withheld from the agent's model" in text
    assert t.final == "Order O-1 is placed."
    raw = json.dumps([e.data for e in t.events])
    assert PLANTED in raw  # the planted line was in Validio's answer ...
    assert PLANTED not in json.dumps(llm.inputs)  # ... and never reached the model
    assert "untrusted" not in json.dumps(llm.inputs).lower()


@pytest.mark.asyncio
async def test_pane_scene3_owner_decides(ctx):
    text, t, llm = await pane(ctx, 3)
    assert "simulated: Stock-out simulated" in text
    assert "not_deliverable" in text and "473986" in text
    assert "mozzarella-fontal blend" in text
    assert "order O-1: waiting, 180.10 €" in text and "10 × 2.5 kg" in text
    assert t.final == "Order O-1 waits for the owner's approval on the phone."
    assert "supplierText" not in json.dumps(llm.inputs)


@pytest.mark.asyncio
@pytest.mark.parametrize("n", [1, 2, 3, 4])
async def test_pane_speaks_like_the_web_app(ctx, n):
    import re
    text, _, _ = await pane(ctx, n)
    shown = "\n".join(ln for ln in text.splitlines() if "agent -> " not in ln and not ln.startswith("kitchen"))
    assert not re.search(r"\b(?:ST|BAG|KI|PAK|PCS|EUR)\b", shown), shown
    assert not re.search(r"\b\d{4,}\.\d\d\b", shown)  # 1,010.00 €, never 1010.00
