"""`validio-agent --scene 2` (or `make agent SCENE=2`): the kitchen's purchasing agent for one scene,
printed for the demo's left pane.

By default it talks MCP to the running Validio of `make demo` on 127.0.0.1:8410, so the web app on the
right shows the same request. Scene 3 needs the presenter's stock-out button first. With --local (or
when nothing answers on the port) it runs Validio's MCP server in process on a fresh seeded store under
a temporary folder, and switches the simulated stock-out on itself for scene 3.

It also writes artifacts/agent/scene-n.md: every tool call, the answer the model saw, the final line.
Scene 4 renews the Steady Order S-1 through the tool renew_steady_order.

With --kitchen k-... it is a kitchen account's agent instead, on /mcp/k/{account}/ of --base (this machine
or the public link): --pair CODE answers the pairing code the Agent page shows with the agent's own key
(kept under --agent-keys), waits for Allow and keeps the Spend Pass; --scene then presents that pass.

The model is Gemini when GEMINI_API_KEY is set, otherwise the fake twin with the same tool calls."""

import argparse
import asyncio
import logging
import os
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

import httpx

from ..config import ROOT
from ..policy.mandate import load_or_create_key
from .buyer import SCENES, run_scene
from .holder import Holder
from .llm import make_llm
from .pane import printer
from .port import McpPort
from .record import write

BASE = "http://127.0.0.1:8410"
ARTIFACTS = ROOT / "artifacts" / "agent"
AGENT_NAME = "Kitchen agent"
PASS_FILE = "pass.sdjwt"


def running(base: str) -> bool:
    try:
        return httpx.get(f"{base}/api/health", timeout=2).status_code == 200
    except httpx.HTTPError:
        return False


def remote(base: str):
    holder = Holder.from_seed(lambda: httpx.get(f"{base}/agent/v1/nonce", timeout=10).json())
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
    holder = Holder.from_seed(lambda: tools.nonce(ctx), ctx.db_path, ctx.keys_dir)
    return server, holder, "Validio in process, fresh seeded store" + (", simulated stock-out of 466375"
                                                                         if scene == 3 else "")


# a kitchen account's agent (--kitchen), paired like any third-party agent (docs/AGENTS.md)


def kitchen_urls(base: str, kitchen: str) -> tuple[str, str]:
    base = base.rstrip("/")
    return f"{base}/mcp/k/{kitchen}/", f"{base}/agent/v1/k/{kitchen}"


def send_pair(http: httpx.Client, kitchen: str, code: str, keys: Path) -> str:
    """Answer the pairing code with this agent's name and public key; the kitchen then sees the consent screen."""
    key = load_or_create_key(Path(keys) / "agent-es256.json")
    r = http.post(f"/agent/v1/k/{kitchen}/pair", json={"code": code, "name": AGENT_NAME,
                                                       "publicJwk": key.export_public(as_dict=True)})
    if r.status_code != 202:
        raise SystemExit(f"pairing refused: {r.status_code} {r.text[:200]}")
    return r.json()["status"]


def wait_pass(http: httpx.Client, kitchen: str, code: str, keys: Path, timeout: float = 120) -> str | None:
    """Poll until the person allows (the pass, kept in keys/pass.sdjwt) or denies; None when time runs out."""
    end = time.monotonic() + timeout
    while True:
        r = http.get(f"/agent/v1/k/{kitchen}/pass", params={"code": code})
        if r.status_code != 200:
            raise SystemExit(f"pass refused: {r.status_code} {r.text[:200]}")
        got = r.json()
        if got["status"] == "denied":
            raise SystemExit("the kitchen denied this agent")
        if got["status"] == "allowed":
            (Path(keys) / PASS_FILE).write_text(got["spendPass"])
            return got["spendPass"]
        if time.monotonic() >= end:
            return None
        time.sleep(0.5)


def kitchen_holder(http: httpx.Client, kitchen: str, keys: Path) -> Holder:
    f = Path(keys) / PASS_FILE
    if not f.is_file():
        raise SystemExit(f"no Spend Pass in {f}, pair first: --kitchen {kitchen} --pair CODE")
    key = load_or_create_key(Path(keys) / "agent-es256.json")
    return Holder(f.read_text().strip(), key, lambda: http.get(f"/agent/v1/k/{kitchen}/nonce").json())


async def _main(scene: int, base: str, force_local: bool, kitchen: str | None = None,
                keys: Path | None = None) -> None:
    target = None
    if kitchen:
        http = httpx.Client(base_url=base.rstrip("/"), timeout=30)
        holder = kitchen_holder(http, kitchen, keys)
        target, label = kitchen_urls(base, kitchen)[0], f"Validio kitchen {kitchen[:10]}... at {base}"
    elif not force_local and running(base):
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
    ap.add_argument("--kitchen", help="a kitchen account's id (k-...): its agent on /mcp/k/{account}/ of --base")
    ap.add_argument("--pair", metavar="CODE", help="with --kitchen: answer the Agent page's pairing code, wait for Allow")
    ap.add_argument("--agent-keys", type=Path, help="with --kitchen: the agent's key and pass "
                                                     "(default artifacts/agent/keys/<account>)")
    ap.add_argument("--wait", type=float, default=120, help="with --pair: seconds to wait for Allow")
    a = ap.parse_args(argv)
    if a.print_pass:
        return print_pass()
    if a.pair and not a.kitchen:
        ap.error("--pair needs --kitchen")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # the pane shows Validio's answers, not HTTP lines
    keys = a.agent_keys or ARTIFACTS / "keys" / (a.kitchen or "local")
    if a.pair:
        with httpx.Client(base_url=a.base.rstrip("/"), timeout=30) as http:
            send_pair(http, a.kitchen, a.pair, keys)
            print(f"{AGENT_NAME} waits for Allow on the Agent page", flush=True)
            if wait_pass(http, a.kitchen, a.pair, keys, a.wait) is None:
                print("not allowed in time", file=sys.stderr)
                return 1
        print(f"connected, Spend Pass kept in {keys / PASS_FILE}", flush=True)
        return 0
    asyncio.run(_main(a.scene, a.base, a.local, a.kitchen, keys))
    return 0
