"""Acceptance: the "Done means" path of the accounts plan through the HTTP API, two demo browsers side by side.

Browser A walks the path: try the demo kitchen, connect the demo agent, send the example request and see it
ordered, lower the alone limit in Rules with the code, send again and see it wait, approve with the code,
pause the agent and see the refusal in the ledger, change the diet in Settings. Browser B holds its own demo
copy the whole time; after every step nothing A did shows in B. At the end B runs the example itself and is
judged on its own limits and its own week.

Numbers: docs/ACCOUNTS-API.md and the demo template the orchestrator fixed (agent not connected at start,
alone up to 1,200.00 €, approval up to 5,000.00 €, demo code 246810; the example request is 1,000 l of
lactose-free milk, 1,010.00 € from the recorded Valio answers, ordered alone; alone limit 800.00 € makes
the same request wait).

Both browsers call from addresses that are not this machine, so only the session cookie lets them in, as on
the public link. The steps share one module-scoped world and run in file order.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

CODE = "246810"
EXAMPLE = "1000 litres of lactose-free milk by Monday, budget 1200 euro"
EXAMPLE_CENTS = 101000
ALONE, APPROVAL = 120000, 500000
LOWER_ALONE = 80000
ROOT = Path(__file__).resolve().parents[3]  # validio/


def template_flags() -> list[str]:
    """The flags `make template` gives demo_check.py, read from the Makefile, so this test plays the same
    template the deploy builds."""
    m = re.search(r"^template:\n\t.*demo_check\.py (.*?)--store", (ROOT / "Makefile").read_text(), re.MULTILINE)
    assert m, "the Makefile has no template target calling demo_check.py --store"
    return m.group(1).split()


@pytest.fixture(scope="module")
def world(tmp_path_factory, catalog):
    """A local kitchen like conftest's ctx, accounts and the demo template under a temporary directory, two
    browsers on two public addresses. The template is played once from the five scenes (make template)."""
    from validio.config import load_settings

    s = load_settings()
    if not any(s.valio_cache.glob("price/*/*.json")):
        pytest.skip("needs_data: no recorded Valio answers, run make record")
    tmp = tmp_path_factory.mktemp("accept")
    template = tmp / "template"
    env_fix = {"VALIDIO_DEMO": "1", "VALIO_MODE": "replay", "GEMINI_API_KEY": "", "VALIDIO_APPROVE_CODE": CODE,
               "VALIDIO_DB": str(tmp / "local" / "validio.db"), "VALIDIO_KEYS": str(tmp / "local" / "keys"),
               "VALIDIO_ACCOUNTS": str(tmp / "accounts"), "VALIDIO_TEMPLATE": str(template)}
    blank = ("VALIDIO_PUBLIC", "VALIDIO_PUBLIC_READ", "VALIDIO_KITCHEN_TOKEN", "VALIDIO_MCP_HOSTS")
    mp = pytest.MonkeyPatch()
    for k, v in env_fix.items():
        mp.setenv(k, v)
    for k in blank:
        mp.setenv(k, "")
    built = subprocess.run([sys.executable, "-W", "ignore", str(ROOT / "scripts" / "demo_check.py"), *template_flags(),
                            "--store", str(template)], check=False, cwd=ROOT / "src" / "backend", env={**os.environ},
                           capture_output=True, text=True, timeout=300)
    assert built.returncode == 0 and (template / "validio.db").is_file(), built.stdout[-2000:] + built.stderr[-2000:]

    from validio.api import accounts as acc_mod
    from validio.api.state import Ctx, set_ctx
    from validio.api.steady import Runtime
    from validio.demo import seed

    (tmp / "local").mkdir(exist_ok=True)
    seed.reset()
    set_ctx(Ctx(Runtime()))
    acc_mod._tries.clear()
    from validio.api.app import app

    with TestClient(app, client=("203.0.113.10", 50001)) as a, TestClient(app, client=("203.0.113.20", 50002)) as b:
        yield {"a": a, "b": b}
    set_ctx(None)
    mp.undo()


def ok(r, status=200):
    assert r.status_code == status, f"{r.request.method} {r.request.url.path}: {r.status_code} {r.text[:400]}"
    return r.json() if r.content else None


def snapshot(c: TestClient) -> dict:
    """Everything of one kitchen that A's steps could leak into."""
    agent = c.get("/api/agent")
    return {"inbox": [(i["id"], i["status"]) for i in ok(c.get("/api/inbox"))],
            "ledger": len(ok(c.get("/api/ledger"))["entries"]),
            "rules": ok(c.get("/api/rules")),
            "diet": ok(c.get("/api/settings"))["diet"],
            "agent": agent.json().get("state") if agent.status_code == 200 else agent.status_code}


def b_untouched(w):
    assert snapshot(w["b"]) == w["b0"], "browser B changed although only A acted"


def pass_is_the_rules(c: TestClient) -> None:
    """The pass the Agent page shows (Technical fold) carries exactly the saved Rules: the current version, not
    the copy an agent showed before the last re-sign."""
    p, r = ok(c.get("/api/spend-passes/M-1")), ok(c.get("/api/rules"))
    shown = (p["autoLimitCents"], p["hardCapCents"], p.get("weekCapCents"))
    assert shown == (r["aloneUpToCents"], r["approvalUpToCents"], r["perWeekCents"]), (shown, r)


def ledger(c: TestClient) -> list[dict]:
    return ok(c.get("/api/ledger"))["entries"]


# 1. Try the demo kitchen

def test_01_try_the_demo_kitchen(world):
    a, b = ok(world["a"].post("/api/account/demo")), ok(world["b"].post("/api/account/demo"))
    assert a["isDemo"] is True and a["demoCode"] == CODE
    assert a["id"] != b["id"], "two browsers share one demo copy"
    assert ok(world["a"].post("/api/account/demo"))["id"] == a["id"], "a reload made a new copy"
    assert a["agent"]["state"] == "none", "the demo template must start with no agent connected"
    world["ids"] = (a["id"], b["id"])
    world["b0"] = snapshot(world["b"])


def test_02_demo_template_numbers(world):
    for c in (world["a"], world["b"]):
        r = ok(c.get("/api/rules"))
        assert (r["aloneUpToCents"], r["approvalUpToCents"], r["saved"]) == (ALONE, APPROVAL, True)
        assert ok(c.get("/api/settings"))["diet"] == ["FREE_FROM_LACTOSE"]
        pass_is_the_rules(c)


def test_01b_without_a_session_the_public_caller_is_refused(world):
    with TestClient(world["a"].app, client=("203.0.113.30", 50003)) as stranger:
        assert stranger.get("/api/inbox").status_code in (401, 403)
        assert stranger.get("/api/account").status_code == 401


# 2. Connect the demo agent

def test_03_connect_the_demo_agent(world):
    a = world["a"]
    aid = world["ids"][0]
    assert ok(a.get("/api/agent"))["state"] == "none"
    led = len(ledger(a))
    p = ok(a.post("/api/agent/pair"))
    assert p["state"] == "pairing"
    assert len(p["pairing"]["code"].replace("-", "")) == 8
    assert re.search(r"/mcp/c/[A-Za-z0-9_-]{43}/$", p["pairing"]["mcpUrl"])  # any MCP agent; signing ones use the code
    assert p["pairing"]["apiUrl"].endswith(f"/agent/v1/k/{aid}")
    c = ok(a.post("/api/agent/demo"))
    assert c["state"] == "consent" and c["consent"]["name"] and c["consent"]["may"]
    assert any("1,200.00 €" in m for m in c["consent"]["may"]), c["consent"]["may"]
    s = ok(a.post("/api/agent/allow"))
    assert s["state"] == "active"
    assert s["agent"]["keyId"] == c["consent"]["keyId"]
    assert s["versions"][0]["why"] == "Agent connected"
    world["version"] = s["agent"]["passVersion"]
    assert ok(a.get("/api/account"))["setup"]["agent"] is True
    new = ledger(a)[led:]
    assert any(e["kind"] == "agent" and e.get("spendPassId") for e in new), [e["sentence"] for e in new]
    assert a.post("/api/agent/allow").status_code == 409, "allow twice"
    pass_is_the_rules(a)
    b_untouched(world)


# 3. Send the example request, see it ordered

def test_04_example_request_is_ordered(world):
    a = world["a"]
    r = ok(a.post("/api/demo/example"))
    rid = r["requestId"]
    assert rid, r["final"]
    v = ok(a.get(f"/api/requests/{rid}"))
    assert v["status"] == "ordered_alone", v.get("decision")
    assert v["totalCents"] == EXAMPLE_CENTS
    assert v["text"] == EXAMPLE
    assert ok(a.get("/api/inbox"))[0]["id"] == rid
    world["first"] = rid
    assert world["b"].get(f"/api/requests/{rid}").status_code == 404 or rid in dict(world["b0"]["inbox"])
    b_untouched(world)


# 4. Lower the limit in Rules with the code

def test_05_lower_the_alone_limit(world):
    a = world["a"]
    before = ok(a.get("/api/rules"))
    body = {"aloneUpToCents": LOWER_ALONE, "approvalUpToCents": APPROVAL, "substitutes": before["substitutes"],
            "maxExtraPct": before["maxExtraPct"]}
    assert a.put("/api/rules", json={**body, "code": "000000"}).status_code == 403
    assert ok(a.get("/api/rules")) == before, "a wrong code changed the Rules"
    led = len(ledger(a))
    r = ok(a.put("/api/rules", json={**body, "code": CODE}))
    assert r["aloneUpToCents"] == LOWER_ALONE and r["approvalUpToCents"] == APPROVAL
    assert r["passVersion"] == before["passVersion"] + 1
    new = ledger(a)[led:]
    assert [e["kind"] for e in new] == ["spend_pass"], [e["sentence"] for e in new]
    agent = ok(a.get("/api/agent"))
    assert agent["state"] == "active", "saving Rules must keep the agent connected"
    assert agent["versions"][0]["why"] == "Rules changed"
    assert agent["agent"]["passVersion"] == r["passVersion"]
    pass_is_the_rules(a)
    b_untouched(world)


# 5. Send again, see it wait

def test_06_same_request_now_waits(world):
    a = world["a"]
    r = ok(a.post("/api/demo/example"))
    rid = r["requestId"]
    assert rid and rid != world.get("first"), r["final"]
    v = ok(a.get(f"/api/requests/{rid}"))
    assert v["status"] == "waiting", f"expected waiting, got {v['status']}: {(v.get('decision') or {}).get('sentence')}"
    assert v["orderId"]
    o = ok(a.get(f"/api/orders/{v['orderId']}"))
    assert o["state"] == "waiting"
    top = ok(a.get("/api/inbox"))[0]
    assert (top["id"], top["status"]) == (rid, "waiting")
    world["waiting"] = (rid, v["orderId"])
    b_untouched(world)


# 6. Approve with the code

def test_07_approve_with_the_code(world):
    a, b = world["a"], world["b"]
    rid, oid = world["waiting"]
    assert b.post(f"/api/orders/{oid}/approve", json={"code": CODE}).status_code == 404 \
        or ok(b.get(f"/api/orders/{oid}"))["state"] != "placed", "B approved A's order"
    assert a.post(f"/api/orders/{oid}/approve", json={"code": "111111"}).status_code == 403
    assert ok(a.get(f"/api/orders/{oid}"))["state"] == "waiting"
    o = ok(a.post(f"/api/orders/{oid}/approve", json={"code": CODE}))
    assert o["state"] == "placed" and o["approvedBy"]
    assert ok(a.get(f"/api/requests/{rid}"))["status"] in ("approved", "ordered")
    b_untouched(world)


# 7. Pause the agent, see the refusal in the ledger

def test_08_pause_and_refusal_in_ledger(world):
    a = world["a"]
    requests_before = [i["id"] for i in ok(a.get("/api/inbox"))]
    s = ok(a.post("/api/agent/pause", json={"paused": True}))
    assert s["state"] == "paused"
    led = len(ledger(a))
    r = ok(a.post("/api/demo/example"))
    assert not r.get("requestId"), "a paused agent got a request through"
    assert "paused" in (r["final"] + " ".join(r["lines"])).lower()
    assert [i["id"] for i in ok(a.get("/api/inbox"))] == requests_before
    refused = [e for e in ledger(a)[led:] if e["kind"] == "agent" and "paused" in e["sentence"].lower()]
    assert len(refused) == 1, [e["sentence"] for e in ledger(a)[led:]]
    assert refused[0].get("spendPassId")
    assert ok(a.get("/api/ledger"))["chain"]["ok"] is True
    assert ok(a.get("/api/agent"))["state"] == "paused"
    b_untouched(world)


# 8. Settings: change the diet

def test_09_change_the_diet(world):
    a = world["a"]
    diet = ["FREE_FROM_GLUTEN", "FREE_FROM_LACTOSE"]
    assert a.put("/api/settings/diet", json={"diet": diet, "code": "000000"}).status_code == 403
    v0 = ok(a.get("/api/rules"))["passVersion"]
    led = len(ledger(a))
    s = ok(a.put("/api/settings/diet", json={"diet": diet, "code": CODE}))
    assert s["diet"] == diet
    assert ok(a.get("/api/settings"))["diet"] == diet
    assert ok(a.get("/api/rules"))["passVersion"] == v0 + 1
    assert [e["kind"] for e in ledger(a)[led:]] == ["spend_pass"]
    assert ok(a.get("/api/agent"))["versions"][0]["why"] == "Diet changed"
    b_untouched(world)


# B on its own: its limits and its week, untouched by everything A did

def test_10_b_runs_the_example_on_its_own_copy(world):
    a, b = world["a"], world["b"]
    a_inbox = ok(a.get("/api/inbox"))
    ok(b.post("/api/agent/pair"))
    ok(b.post("/api/agent/demo"))
    assert ok(b.post("/api/agent/allow"))["state"] == "active"
    assert ok(a.get("/api/agent"))["state"] == "paused", "B's connect touched A's agent"
    r = ok(b.post("/api/demo/example"))
    v = ok(b.get(f"/api/requests/{r['requestId']}"))
    assert v["status"] == "ordered_alone", f"B: {v['status']}: {(v.get('decision') or {}).get('sentence')}"
    assert ok(a.get("/api/inbox")) == a_inbox
    assert ok(b.get("/api/settings"))["diet"] == ["FREE_FROM_LACTOSE"]
