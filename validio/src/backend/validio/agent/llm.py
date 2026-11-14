"""The model behind the kitchen's agent: Gemini when GEMINI_API_KEY is set, otherwise a fixed twin.

Both see the same thing: the task and Validio's answers after `redact`. Both answer with tool calls
from the same five tools. The twin's script is the call sequence the Gemini path is asked to follow."""

import json
import os
from dataclasses import dataclass, field
from typing import Any, Protocol

from .tools import TOOLS

# Stable model code with function calling, checked 2026-11-14 on the Gemini API docs:
# https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash (model code `gemini-3.8-flash`,
# "Function calling: Supported", latest update September 2026) and the supported-models table at
# https://ai.google.dev/gemini-api/docs/function-calling. GEMINI_MODEL overrides it.
DEFAULT_MODEL = "gemini-3.8-flash"

SYSTEM = (
    "You are the purchasing agent of the kitchen hotel-espoo. You buy only through the Validio tools. "
    "Call request_supply with the request lines and the delivery date. Read the result's decision: "
    "if its outcome is 'auto_order', call confirm_order with the request id and, for each line, the "
    "productId and salesQty of that line's 'chosen', then get_order. If the outcome is 'ask_human', "
    "Validio already holds the order for the owner: call get_order with the result's orderId and stop. "
    "If the outcome is 'block', order nothing. If the task names a Steady Order, call renew_steady_order "
    "with its id instead and report which lines were ordered and which wait for the owner. Never invent prices or amounts, take them from Validio's "
    "answer. End with one sentence on what happened.")


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
    """The chosen product and amount of every line, as Validio named it. confirm_order takes only these two."""
    return [{"productId": c["productId"], "salesQty": c["salesQty"]}
            for line in result.get("lines", []) if (c := line.get("chosen"))]


def outcome(result: dict) -> str | None:
    return (result.get("decision") or {}).get("outcome")


class FakeLLM:
    """Deterministic twin for scenes 1 to 4, no key needed."""

    name = "fake model (no Gemini key)"

    def __init__(self, scene: int):
        self.scene = scene
        self.inputs: list = []

    def step(self, history: list[dict[str, Any]]) -> Step:
        self.inputs.append(json.loads(json.dumps(history)))
        task = history[0]
        if task.get("steadyOrder"):
            return self._steady(task, history)
        req, order = _last(history, "request_supply"), _last(history, "confirm_order")
        if self.scene == 1 and not _results(history):
            return Step([ToolCall("search_products", {"text": task["search"], "claims": task["claims"],
                                                      "limit": 5})])
        if req is None:
            return Step([ToolCall("request_supply", {"lines": task["lines"], "deliverBy": task["deliverBy"]})])
        rid = req.get("requestId") or req.get("id")
        out = outcome(req)
        if self.scene == 1:
            live = (req.get("liveChecked") or {}).get("ids")
            what = {"auto_order": "may order", "ask_human": "asks a person about",
                    "block": "blocks"}.get(out, "answered")
            tail = " alone" if out == "auto_order" else ""
            return Step(text=f"Validio {what} request {rid}{tail} ({out}), checked {live} products live.")
        if "error" in req or out not in ("auto_order", "ask_human"):
            why = req.get("error") or (req.get("decision") or {}).get("sentence", "")
            return Step(text=f"Validio blocked request {rid}, nothing ordered. {why}".strip())
        if out == "ask_human":
            if _last(history, "get_order") is None and req.get("orderId"):
                return Step([ToolCall("get_order", {"orderId": req["orderId"]})])
            o = _last(history, "get_order") or {}
            return Step(text=f"Order {o.get('id', req.get('orderId'))} waits for the owner's approval on the phone.")
        if order is None:
            return Step([ToolCall("confirm_order", {"requestId": rid, "choice": chosen(req)})])
        if "error" in order:
            return Step(text=f"Validio refused the order: {order['error']}")
        final = _last(history, "get_order")
        if final is None:
            return Step([ToolCall("get_order", {"orderId": order["id"]})])
        return Step(text=f"Order {final.get('id')} is {final.get('state')}.")


    @staticmethod
    def _steady(task: dict, history: list[dict]) -> Step:
        view = _last(history, "renew_steady_order")
        if view is None:
            return Step([ToolCall("renew_steady_order", {"orderId": task["steadyOrder"]})])
        if "error" in view:
            return Step(text=f"Validio did not renew {task['steadyOrder']}: {view['error']}")
        done, waits = ordered(view), waiting(view)
        parts = [f"{_and(done)} {'is' if len(done) == 1 else 'are'} ordered alone"] if done else []
        if waits:
            parts.append(f"{_and(waits)} wait{'s' if len(waits) == 1 else ''} for the owner")
        return Step(text=f"Steady Order {view.get('id')} is renewed: {', '.join(parts) or 'nothing to do'}.")


def ordered(view: dict) -> list[str]:
    """Steady Order lines Validio ordered alone."""
    return [ln["productId"] for ln in view.get("lines", [])
            if ln.get("result") in ("renewed", "split_renewed") and ln.get("orderId")]


def waiting(view: dict) -> list[str]:
    """Steady Order lines that wait for the owner."""
    done = set(ordered(view))
    return [ln["productId"] for ln in view.get("lines", []) if ln["productId"] not in done
            and ln.get("result") != "accepted"]


def _and(ids: list[str]) -> str:
    return ids[0] if len(ids) == 1 else f"{', '.join(ids[:-1])} and {ids[-1]}"


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
        return cls(key, os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL)

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
