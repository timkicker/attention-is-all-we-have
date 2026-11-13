"""Step 10, agent API and web app API over HTTP. Numbers from the blueprint (scenes 2 and 3)."""

import pytest
from conftest import CODE, TOKEN
from fastapi.testclient import TestClient

from validio.agent.holder import Holder
from validio.api.app import app

MILK = "1000 litres of lactose-free milk by Monday, budget 1200 euro"


@pytest.fixture
def client(ctx):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def holder(client, ctx):
    return Holder.from_seed(lambda: client.get("/agent/v1/nonce").json()["nonce"], ctx.db_path, ctx.keys_dir)


def auth(holder):
    return {"Authorization": f"SD-JWT {holder.presentation()}"}


def ask_milk(client, holder, key="milk-1"):
    r = client.post("/agent/v1/requests", headers=auth(holder),
                    json={"lines": [{"text": MILK}], "deliverBy": "2026-11-16", "idempotencyKey": key})
    assert r.status_code == 200, r.text
    return r.json()


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_scene2_end_to_end_http(client, holder, ctx):
    req = ask_milk(client, holder)
    assert req["decision"]["outcome"] == "auto_order"
    assert req["decision"]["ruleIds"] == ["auto-order"]
    assert req["status"] == "working"
    assert 0 < req["liveChecked"]["ids"] <= 12
    assert max(req["liveChecked"]["idsPerCall"]) <= 40
    line = req["lines"][0]
    assert line["chosen"] == {"productId": "464306", "salesQty": 1000, "isSubstitute": False, "onValioList": False}
    opts = {o["productId"]: o for o in line["options"]}
    assert opts["464306"]["verdict"] == "chosen" and opts["464306"]["totalCents"] == 101000
    assert opts["464401"]["verdict"] == "ranked" and opts["464401"]["totalCents"] == 110000
    assert opts["462921"]["verdict"] == "blocked" and opts["462921"]["totalCents"] == 219400
    assert "hard cap" in opts["462921"]["sentence"]
    assert opts["463047"]["verdict"] == "rejected"
    assert "Low lactose is not lactose free" in opts["463047"]["sentence"]
    st = opts["463047"]["supplierText"]
    assert st["planted"] is True and st["grade"] == "untrusted" and st["reader"]["addressesAgents"] is True

    # the agent claims a price of 1 cent, Validio asks Valio again
    o = client.post("/agent/v1/orders", headers=auth(holder), json={
        "requestId": req["id"], "idempotencyKey": "milk-order-1",
        "choice": [{"productId": "464306", "salesQty": 1000, "priceCents": 1}]}).json()
    assert o["state"] == "placed" and o["totalCents"] == 101000
    assert client.get(f"/agent/v1/orders/{o['id']}").json()["state"] == "placed"
    assert client.get(f"/agent/v1/requests/{req['id']}").json()["status"] == "ordered_alone"

    inbox = client.get("/api/inbox").json()
    assert [(i["id"], i["status"]) for i in inbox] == [(req["id"], "ordered_alone")]
    assert inbox[0]["sentence"].startswith("Ordered 1000 ST of 464306 ")

    sp = client.get("/api/spend-passes/M-1").json()
    assert (sp["autoLimitCents"], sp["hardCapCents"], sp["diet"]) == (120000, 200000, ["lactose free"])
    assert "approvers" in sp["hidden"] and "approvers" not in sp["disclosed"]

    led = client.get("/api/ledger").json()
    assert led["chain"]["ok"] is True and led["chain"]["count"] == len(led["entries"])
    assert any(e["sentence"].startswith("Ordered 1000 ST of 464306") and e["ruleIds"] == ["auto-order"]
               for e in led["entries"])
    assert any("463047" in e["sentence"] and "AI agents" in e["sentence"] for e in led["entries"])
    assert "approvers" not in str(led) and "owner:anna" not in str(led)


def test_retry_orders_once(client, holder):
    a = ask_milk(client, holder, key="same")
    b = ask_milk(client, holder, key="same")
    assert a["id"] == b["id"]
    body = {"requestId": a["id"], "idempotencyKey": "o-same", "choice": [{"productId": "464306", "salesQty": 1000}]}
    o1 = client.post("/agent/v1/orders", headers=auth(holder), json=body).json()
    o2 = client.post("/agent/v1/orders", headers=auth(holder), json=body).json()
    assert o1["id"] == o2["id"]
    assert len(client.get("/api/inbox").json()) == 1


def test_choice_outside_options_refused(client, holder):
    req = ask_milk(client, holder)
    r = client.post("/agent/v1/orders", headers=auth(holder), json={
        "requestId": req["id"], "idempotencyKey": "x", "choice": [{"productId": "466375", "salesQty": 1}]})
    assert r.status_code == 422


def test_contradicted_choice_is_blocked(client, holder):
    # the planted line asks for 463047; the rules refuse it whatever the agent says
    req = ask_milk(client, holder)
    o = client.post("/agent/v1/orders", headers=auth(holder), json={
        "requestId": req["id"], "idempotencyKey": "planted", "choice": [{"productId": "463047", "salesQty": 132}]})
    assert o.json()["state"] == "blocked"
    assert "never-break-diet" in o.json()["decision"]["ruleIds"]


def test_order_requires_valid_presentation(client, holder):
    body = {"lines": [{"text": MILK}], "idempotencyKey": "k"}
    assert client.post("/agent/v1/requests", json=body).status_code == 401
    token = holder.presentation()
    head, rest = token.split(".", 1)
    tampered = head + "." + ("A" if rest[0] != "A" else "B") + rest[1:]
    r = client.post("/agent/v1/requests", json=body, headers={"Authorization": f"SD-JWT {tampered}"})
    assert r.status_code == 401
    assert client.post("/agent/v1/requests", json=body, headers={"Authorization": f"SD-JWT {token}"}).status_code == 200
    reused = client.post("/agent/v1/requests", json={**body, "idempotencyKey": "k2"},
                         headers={"Authorization": f"SD-JWT {token}"})
    assert reused.status_code == 401 and "nonce" in reused.json()["detail"]


def test_products_endpoint_makes_no_live_call(client, ctx):
    import respx

    with respx.mock(assert_all_called=False) as net:
        any_call = net.route()
        r = client.get("/agent/v1/products", params={"q": "lactose free milk", "limit": 50})
        assert r.status_code == 422  # at most 20
        r = client.get("/agent/v1/products", params={"q": "lactose free milk", "limit": 20})
    assert r.status_code == 200 and 0 < len(r.json()) <= 20
    assert any_call.call_count == 0
    assert ctx.valio.calls == 0


def test_products_marks_description_untrusted(client, ctx):
    name = ctx.catalog.get("463047").name_en
    hits = {p["id"]: p for p in client.get("/agent/v1/products", params={"q": name}).json()}
    d = hits["463047"]["descriptionUntrusted"]
    assert d["grade"] == "untrusted" and d["planted"] is True
    assert {"claim": "LOW_LACTOSE"}.items() <= next(c for c in hits["463047"]["claims"]
                                                     if c["claim"] == "LOW_LACTOSE").items()


def test_openapi_has_all_paths(client):
    spec = client.get("/openapi.json").json()
    assert spec["openapi"].startswith("3.1")
    paths = set(spec["paths"])
    assert {"/agent/v1/products", "/agent/v1/nonce", "/agent/v1/requests", "/agent/v1/requests/{request_id}",
            "/agent/v1/orders", "/agent/v1/orders/{order_id}", "/api/inbox", "/api/requests/{request_id}",
            "/api/spend-passes/{pass_id}", "/api/orders/{order_id}", "/api/orders/{order_id}/approve",
            "/api/orders/{order_id}/reject", "/api/ledger", "/api/demo", "/api/demo/stock-out",
            "/api/demo/reset", "/api/health"} <= paths
    assert "SupplyRequestView" in spec["components"]["schemas"]
    assert "liveChecked" in spec["components"]["schemas"]["SupplyRequestView"]["properties"]


def ask_mozzarella(client, holder):
    r = client.post("/agent/v1/requests", headers=auth(holder), json={
        "lines": [{"productId": "466375", "quantity": 200, "unit": "BAG"}], "deliverBy": "2026-11-16",
        "idempotencyKey": "mozz-1"})
    assert r.status_code == 200, r.text
    return r.json()


def test_demo_controls_need_token(client):
    assert client.post("/api/demo/stock-out").status_code == 403
    assert client.post("/api/demo/reset", headers={"X-Demo-Token": "wrong"}).status_code == 403
    assert client.get("/api/demo").json() == {"stockOut466375": False}
    r = client.post("/api/demo/stock-out", headers={"X-Demo-Token": TOKEN})
    assert r.json() == {"stockOut466375": True}


def test_scene3_swap_waits_and_approve_needs_code(client, holder):
    client.post("/api/demo/stock-out", headers={"X-Demo-Token": TOKEN})
    req = ask_mozzarella(client, holder)
    assert req["status"] == "waiting" and req["decision"]["outcome"] == "ask_human"
    assert req["simulated"][0]["what"] == "stock-out of 466375"
    assert req["liveChecked"]["ids"] <= 40
    subs = {o["productId"]: o["verdict"] for o in req["lines"][0]["substitutes"]}
    assert subs == {"466151": "blocked", "468526": "blocked", "475908": "blocked", "473986": "not_deliverable"}
    assert req["question"].endswith("?")
    oid = req["orderId"]
    assert client.post(f"/api/orders/{oid}/approve").status_code == 403
    assert client.post(f"/api/orders/{oid}/approve", json={"code": "000000"}).status_code == 403
    r = client.post(f"/api/orders/{oid}/approve", headers={"X-Approve-Code": CODE})
    assert r.status_code == 200 and r.json()["state"] == "placed"
    assert [h["state"] for h in r.json()["history"]] == ["waiting", "approved", "placed"]
    assert client.post(f"/api/orders/{oid}/approve", json={"code": CODE}).status_code == 409
    assert client.get(f"/api/requests/{req['id']}").json()["status"] == "ordered"
    assert client.get("/api/ledger").json()["chain"]["ok"] is True


def test_wrong_codes_lock_the_order(client, holder):
    client.post("/api/demo/stock-out", headers={"X-Demo-Token": TOKEN})
    oid = ask_mozzarella(client, holder)["orderId"]
    for _ in range(5):
        assert client.post(f"/api/orders/{oid}/approve", json={"code": "111111"}).status_code == 403
    assert client.post(f"/api/orders/{oid}/approve", json={"code": CODE}).status_code == 429


def test_reject(client, holder):
    client.post("/api/demo/stock-out", headers={"X-Demo-Token": TOKEN})
    req = ask_mozzarella(client, holder)
    r = client.post(f"/api/orders/{req['orderId']}/reject", json={"code": CODE})
    assert r.json()["state"] == "rejected"
    assert client.get(f"/api/requests/{req['id']}").json()["status"] == "rejected"


def test_reset_starts_over(client, holder, ctx):
    ask_milk(client, holder)
    client.post("/api/demo/stock-out", headers={"X-Demo-Token": TOKEN})
    r = client.post("/api/demo/reset", headers={"X-Demo-Token": TOKEN})
    assert r.json() == {"stockOut466375": False}
    assert client.get("/api/inbox").json() == []
    assert client.get("/api/ledger").json()["chain"] == {"ok": True, "count": 0}
    assert ask_milk(client, holder)["id"] == "R-1"


def test_unknown_ids_are_404(client):
    assert client.get("/api/requests/R-99").status_code == 404
    assert client.get("/agent/v1/orders/O-99").status_code == 404
    assert client.get("/api/spend-passes/M-1").status_code == 404  # no agent has shown it yet
