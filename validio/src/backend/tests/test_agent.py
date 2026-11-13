"""Step 17, the kitchen's purchasing agent on the five MCP tools.

The fake model twin issues the same tool calls as the Gemini path for scenes 1 to 3. The live Gemini
test runs only with GEMINI_API_KEY set."""

import json
import os

import agent_double
import pytest

from validio.agent.buyer import SCENES, run_scene
from validio.agent.llm import FakeLLM, GeminiLLM
from validio.agent.port import McpPort
from validio.agent.tools import TOOLS, redact


async def scene(n, llm=None):
    server = agent_double.build()
    async with McpPort(server, spend_pass=lambda: "PASS") as port:
        t = await run_scene(n, llm or FakeLLM(n), port)
    return t, list(agent_double.calls)


def test_five_tools_declared():
    assert [t["name"] for t in TOOLS] == [
        "search_products", "request_supply", "get_request", "confirm_order", "get_order"]
    for t in TOOLS:  # the model never writes idempotency keys or the Spend Pass
        assert "idempotencyKey" not in t["parameters"]["properties"]
        assert "spendPass" not in t["parameters"]["properties"]


@pytest.mark.asyncio
async def test_port_sees_five_tools():
    async with McpPort(agent_double.build()) as port:
        assert sorted(await port.tool_names()) == sorted(t["name"] for t in TOOLS)


@pytest.mark.asyncio
async def test_fake_scene1_requests_supply():
    t, calls = await scene(1)
    assert [c for c, _ in calls] == ["search_products", "request_supply"]
    assert calls[1][1]["lines"] == [{"text": SCENES[1].request}]
    assert calls[1][1]["deliverBy"] == "2026-11-16"
    assert t.final.startswith("Validio allows")


@pytest.mark.asyncio
async def test_fake_scene2_orders_alone():
    t, calls = await scene(2)
    assert [c for c, _ in calls] == ["request_supply", "confirm_order", "get_order"]
    assert calls[1][1]["choice"] == [{"productId": "464306", "salesQty": 1000}]
    assert calls[1][1]["requestId"] == "R-1"
    assert "placed" in t.final


@pytest.mark.asyncio
async def test_fake_scene3_hands_swap_to_owner():
    t, calls = await scene(3)
    assert [c for c, _ in calls] == ["request_supply", "confirm_order", "get_order"]
    assert calls[0][1]["lines"] == [{"productId": "466375", "quantity": 200, "unit": "BAG"}]
    assert calls[1][1]["choice"] == [{"productId": "465256", "salesQty": 10, "isSubstitute": True,
                                      "onValioList": False}]
    assert "owner" in t.final


@pytest.mark.asyncio
async def test_port_adds_spend_pass_and_stable_idempotency_keys():
    _, a = await scene(2)
    _, b = await scene(2)
    assert a[0][1]["spendPass"] == "PASS"
    assert a[0][1]["idempotencyKey"] == b[0][1]["idempotencyKey"]
    assert a[1][1]["idempotencyKey"] != a[0][1]["idempotencyKey"]


@pytest.mark.asyncio
@pytest.mark.parametrize("n", [1, 2, 3])
async def test_buyer_never_sees_supplier_text(n):
    llm = FakeLLM(n)
    t, _ = await scene(n, llm)
    seen = json.dumps(llm.inputs)
    raw = json.dumps([e.data for e in t.events])
    for text in (agent_double.PLANTED, agent_double.MARKETING, "CHEESE (MILK)", "Fresh Finnish milk"):
        assert text not in seen
    if n == 1:
        assert agent_double.PLANTED in raw  # it was in Validio's answer, the agent's model just never got it


def test_redact_drops_every_supplier_text_field():
    out = redact({"a": [{"descriptionUntrusted": "x", "marketing_en": "y", "keyIngredients": "z",
                         "plantedLine": "p", "supplierText": "s", "name": "kept"}]})
    assert out == {"a": [{"name": "kept"}]}


@pytest.mark.asyncio
@pytest.mark.skipif(not os.environ.get("GEMINI_API_KEY"),
                    reason="LIVE GEMINI SKIPPED: GEMINI_API_KEY is not set, only the fake twin ran")
async def test_gemini_buyer_scene2_three_runs_same_order():
    orders = []
    for _ in range(3):
        llm = GeminiLLM.from_env()
        _, calls = await scene(2, llm)
        assert agent_double.PLANTED not in json.dumps(llm.inputs)
        orders.append([c[1]["choice"] for c in calls if c[0] == "confirm_order"])
    assert orders[0] == orders[1] == orders[2] == [[{"productId": "464306", "salesQty": 1000}]]


def test_gemini_path_builds_offline():
    llm = GeminiLLM("not-a-key", "gemini-test")  # no network call on construction
    decls = llm._config.tools[0].function_declarations
    assert [d.name for d in decls] == [t["name"] for t in TOOLS]
    assert llm._config.automatic_function_calling.disable
    history = [{"role": "user", "text": "task"},
               {"role": "model", "calls": [{"name": "request_supply", "args": {"lines": []}}]},
               {"role": "tool", "name": "request_supply", "result": {"status": "allowed"}}]
    c = llm._contents(history)
    assert [x.role for x in c] == ["user", "model", "user"]
    assert c[1].parts[0].function_call.name == "request_supply"
    assert c[2].parts[0].function_response.response == {"result": {"status": "allowed"}}
