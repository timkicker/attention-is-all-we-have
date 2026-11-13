"""The transcript of one agent run as Markdown, for the video and for judges.

It holds what the model was given, nothing more: the task, every tool call with the model's own
arguments (the port adds the Spend Pass and idempotency keys later, so they are never here), Validio's
answer after `redact`, and the final line. Supplier text is counted, not shown."""

import json
from pathlib import Path

from .buyer import SCENES, Transcript, _assert_clean
from .pane import _withheld
from .tools import redact


def markdown(t: Transcript, scene: int, target: str) -> str:
    out = [f"# Agent transcript, scene {scene}: {SCENES[scene].title}", "",
           f"- model: {t.model}", f"- Validio: {target}", ""]
    n = 0
    for e in t.events:
        if e.kind == "task":
            out += ["## Task", "", str(e.data), ""]
        elif e.kind == "call":
            n += 1
            out += [f"## Call {n}: `{e.name}`", "", "Arguments from the model:", "", "```json",
                    json.dumps(e.data, indent=2, ensure_ascii=False), "```", ""]
        elif e.kind == "answer":
            clean = redact(e.data)
            _assert_clean(clean)
            out += ["Validio's answer as the model saw it:", "", "```json",
                    json.dumps(clean, indent=2, ensure_ascii=False), "```", ""]
            if k := _withheld(e.data):
                out += [f"{k} supplier text fields withheld from the model.", ""]
        elif e.kind == "final":
            out += ["## Final line", "", str(e.data), ""]
    return "\n".join(out)


def write(t: Transcript, scene: int, target: str, folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"scene-{scene}.md"
    path.write_text(markdown(t, scene, target))
    return path
