"""The kitchen's purchasing agent: a loop of model step, MCP tool call, redacted answer back.

The transcript keeps Validio's full answers for the terminal pane. The model gets only the redacted
copy, so supplier text never reaches it."""

from dataclasses import dataclass, field
from typing import Any

from .llm import LLM
from .port import McpPort
from .tools import SUPPLIER_TEXT, redact

DELIVER_BY = "2026-11-16"


@dataclass(frozen=True)
class Scene:
    title: str
    request: str
    lines: list[dict]
    search: str | None = None
    claims: tuple[str, ...] = ()


SCENES = {
    1: Scene("Request", "1000 litres of lactose-free milk by Monday, budget 1200 euro",
             [{"text": "1000 litres of lactose-free milk by Monday, budget 1200 euro"}],
             search="lactose free milk", claims=("FREE_FROM_LACTOSE",)),
    2: Scene("Ordered alone", "1000 litres of lactose-free milk by Monday, budget 1200 euro",
             [{"text": "1000 litres of lactose-free milk by Monday, budget 1200 euro"}]),
    3: Scene("Owner approves a swap", "200 bags of Gran Castelli lactose-free mozzarella 466375 by Monday",
             [{"productId": "466375", "quantity": 200, "unit": "BAG"}]),
}


@dataclass
class Event:
    kind: str  # task, call, answer, final
    name: str
    data: Any


@dataclass
class Transcript:
    model: str
    events: list[Event] = field(default_factory=list)

    @property
    def final(self) -> str:
        return next((e.data for e in reversed(self.events) if e.kind == "final"), "")


def _assert_clean(obj: Any) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if SUPPLIER_TEXT.search(k):
                raise AssertionError(f"supplier text field {k!r} would reach the model")
            _assert_clean(v)
    elif isinstance(obj, list):
        for v in obj:
            _assert_clean(v)


async def run(task: dict[str, Any], llm: LLM, port: McpPort, max_steps: int = 8,
              on_event=None) -> Transcript:
    t = Transcript(llm.name)

    def emit(e: Event) -> None:
        t.events.append(e)
        if on_event:
            on_event(e)

    emit(Event("task", "task", task["text"]))
    history: list[dict[str, Any]] = [{"role": "user", **task}]
    for _ in range(max_steps):
        step = llm.step(history)
        if not step.calls:
            emit(Event("final", "final", step.text or ""))
            return t
        history.append({"role": "model", "calls": [{"name": c.name, "args": c.args} for c in step.calls]})
        for c in step.calls:
            emit(Event("call", c.name, c.args))
            answer = await port.call(c.name, c.args)
            emit(Event("answer", c.name, answer))
            clean = redact(answer)
            _assert_clean(clean)
            history.append({"role": "tool", "name": c.name, "result": clean})
    emit(Event("final", "final", f"Stopped after {max_steps} steps without an answer."))
    return t


def task_for(n: int) -> dict[str, Any]:
    s = SCENES[n]
    text = (f"Kitchen request: {s.request}. Request lines: {s.lines}. Deliver by {DELIVER_BY}.")
    return {"text": text, "lines": s.lines, "deliverBy": DELIVER_BY, "search": s.search,
            "claims": list(s.claims)}


async def run_scene(n: int, llm: LLM, port: McpPort, on_event=None) -> Transcript:
    return await run(task_for(n), llm, port, on_event=on_event)
