"""The transcript recorder: `make agent SCENE=n` also writes artifacts/agent/scene-n.md with every tool
call, the redacted answer the model saw and the final line. No Spend Pass, no keys, no supplier text."""

import pytest

from validio.agent.buyer import run_scene
from validio.agent.holder import Holder
from validio.agent.llm import FakeLLM
from validio.agent.port import McpPort
from validio.agent.record import write
from validio.api import tools
from validio.api.mcp_server import server


@pytest.mark.parametrize("n", [2, 3, 4])
@pytest.mark.asyncio
async def test_transcript_has_calls_answers_final_and_no_secrets(ctx, tmp_path, n):
    if n == 3:
        ctx.set_stockout(True)
    h = Holder.from_seed(lambda: tools.nonce(ctx).nonce, ctx.db_path, ctx.keys_dir)
    passes = []

    def spend_pass():
        passes.append(h.presentation())
        return passes[-1]

    async with McpPort(server, spend_pass=spend_pass) as port:
        t = await run_scene(n, FakeLLM(n), port)
    path = write(t, n, "Validio in process", tmp_path)
    assert path == tmp_path / f"scene-{n}.md"
    md = path.read_text()
    calls = [e for e in t.events if e.kind == "call"]
    assert md.count("\n## Call ") == len(calls)
    for e in calls:
        assert f"`{e.name}`" in md
    assert md.rstrip().endswith(t.final)
    assert passes and not any(p in md for p in passes)  # no Spend Pass bytes
    assert passes[0].split(".")[0] not in md
    assert '"spendPass"' not in md  # spendPassId (the pass's id, M-1) is fine, the pass itself never
    for word in ("idempotencyKey", "supplierText", "untrusted", "AI agents", "descriptionUntrusted"):
        assert word not in md, word


@pytest.mark.asyncio
async def test_transcript_counts_withheld_supplier_text(ctx, tmp_path):
    h = Holder.from_seed(lambda: tools.nonce(ctx).nonce, ctx.db_path, ctx.keys_dir)
    async with McpPort(server, spend_pass=h.presentation) as port:
        t = await run_scene(2, FakeLLM(2), port)
    md = write(t, 2, "Validio in process", tmp_path).read_text()
    assert "supplier text fields withheld" in md
    assert "liveChecked" in md  # Validio's own numbers stay
