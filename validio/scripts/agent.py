"""`make agent SCENE=2`: run the kitchen's purchasing agent for one scene and print the pane.

Uses lane B2's MCP server when `validio.api.mcp_server` exists, otherwise the stand-in server. The
model is Gemini when GEMINI_API_KEY is set, otherwise the fake twin."""

import argparse
import asyncio
import importlib

from validio.agent.buyer import SCENES, run_scene
from validio.agent.llm import make_llm
from validio.agent.pane import printer
from validio.agent.port import McpPort


def server_for(scene: int):
    try:
        mod = importlib.import_module("validio.api.mcp_server")
    except ModuleNotFoundError:
        from validio.agent.standin import build

        return build(stockout=scene == 3), "stand-in (B2's MCP server is not on main yet)"
    return getattr(mod, "server", None) or mod.build_server(), "validio.api.mcp_server"


async def main(scene: int) -> None:
    server, label = server_for(scene)
    llm = make_llm(scene)
    title = SCENES[scene].title
    print(f"Validio demo, scene {scene}: {title}\nmodel: {llm.name} | server: {label}"
          + (" | stock-out of 466375 simulated" if scene == 3 else "") + "\n")
    async with McpPort(server, spend_pass=lambda: "demo-pass-M-1") as port:
        await run_scene(scene, llm, port, on_event=printer())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", type=int, default=2, choices=sorted(SCENES))
    asyncio.run(main(ap.parse_args().scene))
