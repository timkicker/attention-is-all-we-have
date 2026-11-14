"""Test helpers in place of the demo shortcuts Validio no longer has: the scene 3 stock-out set in the store,
the demo agent's key paired the way any signing agent pairs, and a request placed by the kitchen's agent
over MCP (in process, the fake model without a key)."""

import asyncio
import secrets
from dataclasses import dataclass

EXAMPLE = "1000 litres of lactose-free milk by Monday, budget 1200 euro"


def stockout(ctx=None, on: bool = True) -> None:
    """The simulated stock-out of 466375, with its ledger entry; the local kitchen when no ctx is given."""
    from validio.api.state import get_ctx

    (ctx or get_ctx()).set_stockout(on)


def pair_demo_agent(ctx) -> None:
    """The demo agent's key answers a fresh pairing code, as POST /agent/v1/pair does: the kitchen sees consent."""
    from validio.api import connect

    code = connect.pair(ctx).code
    connect.agent_pair(ctx, connect.PairIn(code=code, name=connect.DEMO_AGENT,
                                           public_jwk=connect.demo_key(ctx).export_public(as_dict=True)))


def connect_demo_agent(ctx) -> None:
    """Pair the demo agent and press Allow."""
    from validio.api import connect

    pair_demo_agent(ctx)
    connect.allow(ctx)


@dataclass
class Asked:
    request_id: str | None
    final: str
    lines: list[str]
    model: str


def ask(ctx, text: str) -> Asked:
    """The kitchen's agent (demo key) asks for `text` over Validio's MCP server, in process."""
    from validio.agent.buyer import run, task_for_text
    from validio.agent.holder import Holder
    from validio.agent.llm import make_llm
    from validio.agent.pane import Style, render
    from validio.agent.port import McpPort
    from validio.api import tools
    from validio.api.mcp_server import server
    from validio.api.state import current

    holder = Holder.from_seed(lambda: tools.nonce(ctx), ctx.db_path, ctx.keys_dir)

    async def go():
        async with McpPort(server, spend_pass=holder.presentation, salt=secrets.token_hex(8)) as port:
            return await run(task_for_text(" ".join(text.split())), make_llm(2), port)

    token = current.set(ctx)
    try:
        t = asyncio.run(go())
    finally:
        current.reset(token)
    rid = next((e.data.get("requestId") or e.data.get("id") for e in t.events
                if e.kind == "answer" and e.name == "request_supply" and isinstance(e.data, dict)
                and "error" not in e.data), None)
    return Asked(rid, t.final, [render(e, Style(False)) for e in t.events], t.model)
