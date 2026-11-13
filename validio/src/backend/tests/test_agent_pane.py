"""`make agent SCENE=n`: the pane prints the agent's calls and Validio's real answers (stand-in server
on the recorded Valio answers until lane B2's MCP server lands)."""

import io

import pytest

from validio.agent.buyer import run_scene
from validio.agent.llm import FakeLLM
from validio.agent.pane import printer
from validio.agent.port import McpPort


async def pane(n):
    from validio.agent.standin import build

    out = io.StringIO()
    async with McpPort(build(stockout=n == 3)) as port:
        t = await run_scene(n, FakeLLM(n), port, on_event=printer(color=False, out=out))
    return out.getvalue(), t


@pytest.mark.asyncio
async def test_pane_scene2_orders_464306_alone(catalog):
    text, t = await pane(2)
    assert "agent -> request_supply" in text and "agent -> confirm_order" in text
    assert "checked 12 products live" in text
    assert "464306" in text and "1000 ST  1010.00 EUR" in text
    assert "decision: auto_order (auto-order)" in text
    assert "order O-1: placed, 1010.00 EUR" in text
    assert t.final == "Order O-1 is placed."


@pytest.mark.asyncio
async def test_pane_scene3_owner_decides(catalog):
    text, t = await pane(3)
    assert "Only 0 BAG in stock, 200 needed" in text
    assert "undeliverable          473986" in text
    assert "A mozzarella-fontal blend, not pure mozzarella" in text
    assert "order O-1: waiting, 180.10 EUR" in text
    assert "owner" in t.final


@pytest.mark.asyncio
async def test_pane_scene1_marks_withheld_supplier_text(catalog):
    text, _ = await pane(1)
    assert "agent -> search_products" in text and "status allowed" in text
    assert "supplier text fields withheld from the agent's model" in text
