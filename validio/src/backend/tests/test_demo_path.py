"""The juror's path on a fresh copy of the demo template (orchestrator, 14 Nov): the template is built the way
`make template` and Modal fill() build it (five scenes, then the demo Rules), a browser takes a demo copy,
connects the demo agent (the server's fake twin) and sends the example request: 1,000 l milk for 1,010.00 €
is ordered alone. The juror lowers alone to 800 €, the same request waits, 246810 approves it. Never blocked,
although O-1 and O-2 already used 1,190.10 € of the pass."""

import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from validio.api import accounts as acc_mod
from validio.api.settings import DEMO_RULES

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "demo_check.py"


@pytest.fixture(scope="module")
def template(tmp_path_factory, catalog):
    store = tmp_path_factory.mktemp("template")
    run = subprocess.run([sys.executable, "-W", "ignore", str(SCRIPT), "--rounds", "1", "--template",
                          "--store", str(store)], capture_output=True, text=True, timeout=300, check=False,
                         env={**__import__("os").environ, "VALIO_MODE": "replay"})
    assert run.returncode == 0 and "ALL SCENES OK" in run.stdout, run.stdout[-2000:] + run.stderr[-2000:]
    return store


@pytest.fixture
def juror(ctx, template, tmp_path, monkeypatch):
    monkeypatch.setenv("VALIDIO_ACCOUNTS", str(tmp_path / "accounts"))
    monkeypatch.setenv("VALIDIO_TEMPLATE", str(template))
    acc_mod._tries.clear()
    from validio.api.app import app

    with TestClient(app, client=("203.0.113.7", 50000)) as c:  # a browser elsewhere: only its session opens /api
        yield c


def example(c) -> dict:
    r = c.post("/api/demo/example")
    assert r.status_code == 200, r.text
    rid = r.json()["requestId"]
    return c.get(f"/api/requests/{rid}").json()


def test_template_starts_unconnected_with_the_demo_rules(juror):
    a = juror.post("/api/account/demo").json()
    assert a["isDemo"] and a["demoCode"] == "246810"
    assert a["agent"]["state"] == "none"
    rules = juror.get("/api/rules").json()
    assert {k: rules[k] for k in DEMO_RULES} == DEMO_RULES and rules["saved"] is True
    assert juror.post("/api/demo/example").status_code == 409  # connect the demo agent first


def test_ordered_then_waits_then_approved(juror):
    juror.post("/api/account/demo")
    assert juror.post("/api/agent/demo").json()["state"] == "consent"
    assert juror.post("/api/agent/allow").json()["state"] == "active"

    first = example(juror)
    assert first["decision"]["outcome"] == "auto_order", first["decision"]
    o1 = juror.get(f"/api/orders/{first['orderId']}").json()
    assert o1["state"] == "placed" and o1["totalCents"] == 101000

    r = juror.put("/api/rules", json={**DEMO_RULES, "aloneUpToCents": 80000, "code": "246810"})
    assert r.status_code == 200, r.text

    second = example(juror)
    assert second["decision"]["outcome"] == "ask_human", second["decision"]
    assert second["status"] == "waiting"
    o2 = second["orderId"]
    assert juror.get(f"/api/orders/{o2}").json()["state"] == "waiting"

    assert juror.post(f"/api/orders/{o2}/approve", json={"code": "000000"}).status_code == 403
    done = juror.post(f"/api/orders/{o2}/approve", json={"code": "246810"})
    assert done.status_code == 200, done.text
    assert done.json()["state"] == "placed"
