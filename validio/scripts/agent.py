"""`make agent SCENE=2`: the kitchen's purchasing agent for one scene, printed for the demo's left pane.

By default it talks MCP to the running Validio of `make demo` on 127.0.0.1:8410, so the web app on the
right shows the same request. Scene 3 needs the presenter's stock-out button first. With --local (or
when nothing answers on the port) it runs Validio's MCP server in process on a fresh seeded store under
a temporary folder, and switches the simulated stock-out on itself for scene 3.

The model is Gemini when GEMINI_API_KEY is set, otherwise the fake twin with the same tool calls."""

import argparse
import asyncio
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "backend"))
from validio.agent.buyer import SCENES, run_scene
from validio.agent.holder import Holder
from validio.agent.llm import make_llm
from validio.agent.pane import printer
from validio.agent.port import McpPort

BASE = "http://127.0.0.1:8410"


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
    from validio.api import tools
    from validio.api.mcp_server import server
    from validio.api.state import get_ctx
    from validio.demo import seed

    seed.reset()
    ctx = get_ctx()
    if scene == 3:
        ctx.set_stockout(True)
    holder = Holder.from_seed(lambda: tools.nonce(ctx).nonce, ctx.db_path, ctx.keys_dir)
    return server, holder, "Validio in process, fresh seeded store" + (", simulated stock-out of 466375"
                                                                         if scene == 3 else "")


async def main(scene: int, base: str, force_local: bool) -> None:
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
        await run_scene(scene, llm, port, on_event=printer())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", type=int, default=2, choices=sorted(SCENES))
    ap.add_argument("--base", default=BASE)
    ap.add_argument("--local", action="store_true", help="Validio in process instead of the running server")
    a = ap.parse_args()
    asyncio.run(main(a.scene, a.base, a.local))
