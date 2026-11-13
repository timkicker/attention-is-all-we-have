"""scripts/loadtest.py on a small scale: its own server in replay mode, a few agents at once, every order
placed, no error, and Valio asked about at most 40 distinct ids per request."""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "loadtest.py"


def test_three_agents_two_rounds():
    spec = importlib.util.spec_from_file_location("loadtest", SCRIPT)
    lt = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lt)
    res = lt.run_level(3, 2)
    assert (res["errors"], res["placed"], res["scenes"]) == (0, 6, 6)
    assert set(res["routes"]) == {"GET /agent/v1/nonce", "POST /agent/v1/requests", "POST /agent/v1/orders",
                                  "GET /agent/v1/orders/{id}"}
    budgets = res["server"]["budgets"]
    assert budgets and max(b["ids"] for b in budgets) <= 40
    assert res["server"]["db_locked"] == 0
    assert "N=3 (scene2)" in lt.report(res)
