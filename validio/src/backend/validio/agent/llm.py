"""The model behind the kitchen's agent: Gemini when GEMINI_API_KEY is set, otherwise a fixed twin.

Both see the same thing: the task and Validio's answers after `redact`. Both answer with tool calls
from the same five tools. The twin's script is the call sequence the Gemini path is asked to follow."""

import json
import os
from dataclasses import dataclass, field
from typing import Any, Protocol

from .tools import TOOLS

SYSTEM = (
    "You are the purchasing agent of the kitchen hotel-espoo. You buy only through the Validio tools. "
    "Call request_supply with the request lines and the delivery date. If the result's status is "
    "'allowed', call confirm_order with the request id and the chosen product and amount of each line, "
    "then get_order. If the status is 'ask', confirm the chosen option so the owner can approve it on "
    "the phone, then get_order. If the status is 'blocked', order nothing. Never invent prices or "
    "amounts, take them from Validio's answer. End with one sentence on what happened."
)


@dataclass
class ToolCall:
    name: str
    args: dict[str, Any]


@dataclass
class Step:
    calls: list[ToolCall] = field(default_factory=list)
    text: str | None = None  # the final sentence when there are no calls


class LLM(Protocol):
    name: str
    inputs: list  # everything the model was shown, for the supplier-text check

    def step(self, history: list[dict[str, Any]]) -> Step: ...


def _results(history: list[dict]) -> list[dict]:
    return [h for h in history if h["role"] == "tool"]


def _last(history: list[dict], tool: str) -> dict | None:
    return next((h["result"] for h in reversed(_results(history)) if h["name"] == tool), None)


def chosen(result: dict) -> list[dict]:
    """The chosen product and amount of every line, as Validio named it."""
    out = []
    for line in result.get("lines", []):
        c = line.get("chosen")
        if c:
            out.append({k: c[k] for k in ("productId", "salesQty", "isSubstitute", "onValioList") if k in c})
    return out


class FakeLLM:
    """Deterministic twin for scenes 1 to 3, no key needed."""

    name = "fake model (no Gemini key)"

    def __init__(self, scene: int):
        self.scene = scene
        self.inputs: list = []

    def step(self, history: list[dict[str, Any]]) -> Step:
        self.inputs.append(json.loads(json.dumps(history)))
        task = history[0]
        req, order = _last(history, "request_supply"), _last(history, "confirm_order")
        if self.scene == 1 and not _results(history):
            return Step([ToolCall("search_products", {"text": task["search"], "claims": task["claims"],
                                                      "limit": 5})])
        if req is None:
            return Step([ToolCall("request_supply", {"lines": task["lines"], "deliverBy": task["deliverBy"]})])
        status = req.get("status")
        if self.scene == 1:
            return Step(text=f"Validio {'allows' if status == 'allowed' else 'says ' + str(status)} "
                             f"request {req.get('requestId')}, checked {req.get('liveChecked', {}).get('ids')} "
                             f"products live.")
        if status == "blocked" or "error" in req:
            return Step(text=f"Validio blocked the request, nothing ordered: {req.get('error', '')}".strip())
        if order is None:
            return Step([ToolCall("confirm_order", {"requestId": req["requestId"], "choice": chosen(req)})])
        if _last(history, "get_order") is None and "id" in order:
            return Step([ToolCall("get_order", {"orderId": order["id"]})])
        final = _last(history, "get_order") or order
        if order.get("state") == "waiting":
            return Step(text=f"Order {order['id']} waits for the owner's approval on the phone.")
        return Step(text=f"Order {final.get('id')} is {final.get('state')}.")


class GeminiLLM:
    """Gemini function calling over the same five tools. Automatic calling is off: the buyer runs
    every call through the MCP port itself."""

    def __init__(self, api_key: str, model: str):
        from google import genai
        from google.genai import types

        self._types = types
        self._client = genai.Client(api_key=api_key)
        self.model = model
        self.name = f"Gemini {model}"
        self.inputs: list = []
        self._config = types.GenerateContentConfig(
            system_instruction=SYSTEM, temperature=0,
            tools=[types.Tool(function_declarations=[
                types.FunctionDeclaration(name=t["name"], description=t["description"],
                                          parameters_json_schema=t["parameters"]) for t in TOOLS])],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

    @classmethod
    def from_env(cls) -> "GeminiLLM":
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        return cls(key, os.environ.get("GEMINI_MODEL") or "gemini-2.5-flash")

    def _contents(self, history: list[dict]) -> list:
        t = self._types
        out = []
        for h in history:
            if h["role"] == "user":
                out.append(t.Content(role="user", parts=[t.Part(text=h["text"])]))
            elif h["role"] == "model":
                out.append(t.Content(role="model", parts=[
                    t.Part(function_call=t.FunctionCall(name=c["name"], args=c["args"])) for c in h["calls"]]))
            else:
                out.append(t.Content(role="user", parts=[
                    t.Part.from_function_response(name=h["name"], response={"result": h["result"]})]))
        return out

    def step(self, history: list[dict[str, Any]]) -> Step:
        self.inputs.append(json.loads(json.dumps(history)))
        r = self._client.models.generate_content(model=self.model, contents=self._contents(history),
                                                 config=self._config)
        calls = [ToolCall(fc.name, dict(fc.args or {})) for fc in (r.function_calls or [])]
        return Step(calls, None if calls else (r.text or "").strip())


def make_llm(scene: int) -> LLM:
    return GeminiLLM.from_env() if os.environ.get("GEMINI_API_KEY") else FakeLLM(scene)
