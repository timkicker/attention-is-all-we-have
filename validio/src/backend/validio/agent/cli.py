"""`validio-agent --scene 2` (or `make agent SCENE=2`): the kitchen's purchasing agent for one scene,
printed for the demo's left pane.

By default it talks MCP to the running Validio of `make demo` on 127.0.0.1:8410, so the web app on the
right shows the same request. Scene 3 needs the presenter's stock-out button first. With --local (or
when nothing answers on the port) it runs Validio's MCP server in process on a fresh seeded store under
a temporary folder, and switches the simulated stock-out on itself for scene 3.

It also writes artifacts/agent/scene-n.md: every tool call, the answer the model saw, the final line.
Scene 4 renews the Steady Order S-1 through the tool renew_steady_order.

The model is Gemini when GEMINI_API_KEY is set, otherwise the fake twin with the same tool calls."""

import argparse
import asyncio
import logging
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

import httpx

from ..config import ROOT
from .buyer import SCENES, run_scene
from .holder import Holder
from .llm import make_llm
from .pane import printer
from .port import McpPort
from .record import write

BASE = "http://127.0.0.1:8410"
ARTIFACTS = ROOT / "artifacts" / "agent"


def running(base: str) -> bool:
    try:
        return httpx.get(f"{base}/api/health", timeout=2).status_code == 200
    except httpx.HTTPError:
        return False


def remote(base: str):
    holder = Holder.from_seed(lambda: httpx.get(f"{base}/agent/v1/nonce", timeout=10).json()["nonce"])
    return f"{base}/mcp/", holder, f"Validio at {base}"


def local(scene: int):
    tmp = Path(tempfile.mkdtemp(prefix="validio-agent-"))
    os.environ["VALIDIO_DB"], os.environ["VALIDIO_KEYS"] = str(tmp / "validio.db"), str(tmp / "keys")
    from ..api import tools
    from ..api.mcp_server import server
    from ..api.state import get_ctx
    from ..demo import seed

    seed.reset()
    ctx = get_ctx()
    if scene == 3:
        ctx.set_stockout(True)
    holder = Holder.from_seed(lambda: tools.nonce(ctx).nonce, ctx.db_path, ctx.keys_dir)
    return server, holder, "Validio in process, fresh seeded store" + (", simulated stock-out of 466375"
                                                                         if scene == 3 else "")


async def _main(scene: int, base: str, force_local: bool) -> None:
    target = None
    if not force_local and running(base):
        try:
            target, holder, label = remote(base)
        except sqlite3.Error:
            print(f"Validio answers at {base}, but this checkout has no seeded Spend Pass (run make seed "
                  "or make demo here). Running in process instead.\n", flush=True)
    if target is None:
        target, holder, label = local(scene)
    llm = make_llm(scene)
    print(f"Validio demo, scene {scene}: {SCENES[scene].title}\nmodel: {llm.name} | {label}\n", flush=True)
    async with McpPort(target, spend_pass=holder.presentation) as port:
        t = await run_scene(scene, llm, port, on_event=printer())
    path = write(t, scene, label, ARTIFACTS)
    print(f"transcript: {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}", flush=True)


def print_pass() -> int:
    """The issued Spend Pass M-1 from the seeded store, for a third-party agent (docs/AGENTS.md)."""
    from ..demo import seed

    con = sqlite3.connect(seed.db_path())
    try:
        (issuance,) = con.execute("select issuance from spend_pass where id = ?", (seed.SPEND_PASS_ID,)).fetchone()
    except (sqlite3.Error, TypeError):
        print(f"no seeded Spend Pass in {seed.db_path()}, run make seed first", file=sys.stderr)
        return 1
    finally:
        con.close()
    print(issuance)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="validio-agent", description="The kitchen's purchasing agent for the demo pane.")
    ap.add_argument("--scene", type=int, default=2, choices=sorted(SCENES))
    ap.add_argument("--base", default=BASE)
    ap.add_argument("--local", action="store_true", help="Validio in process instead of the running server")
    ap.add_argument("--print-pass", action="store_true", help="print the seeded Spend Pass for another agent")
    a = ap.parse_args(argv)
    if a.print_pass:
        return print_pass()
    logging.getLogger("httpx").setLevel(logging.WARNING)  # the pane shows Validio's answers, not HTTP lines
    asyncio.run(_main(a.scene, a.base, a.local))
    return 0
