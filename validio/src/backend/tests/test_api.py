"""Step 10, agent API and web app API over HTTP. Numbers from the blueprint (scenes 2 and 3)."""

import re

import pytest
from asking import stockout
from conftest import CODE
from fastapi.testclient import TestClient

from validio.agent.holder import Holder
from validio.api.app import app

VALIO = {"valioDown": False, "valioMode": "replay", "valioModeText": "Valio's recorded answers"}
MILK = "1000 litres of lactose-free milk by Monday, budget 1200 euro"


@pytest.fixture
def client(ctx):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def holder(client, ctx):
    return Holder.from_seed(lambda: client.get("/agent/v1/nonce").json(), ctx.db_path, ctx.keys_dir)


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
    assert st["planted"] is True and st["grade"] == "untrusted"
    assert set(st["reader"]) == {"flags", "summary"}  # the reader's fixed shape, nothing else
    assert {"code": "addresses_agents", "text": "AI agents"} in st["reader"]["flags"]
    assert "never used for decisions" in st["reader"]["summary"]

    # the agent claims a price of 1 cent, Validio asks Valio again
    o = client.post("/agent/v1/orders", headers=auth(holder), json={
        "requestId": req["id"], "idempotencyKey": "milk-order-1",
        "choice": [{"productId": "464306", "salesQty": 1000, "priceCents": 1}]}).json()
    assert o["state"] == "placed" and o["totalCents"] == 101000
    assert client.get(f"/agent/v1/orders/{o['id']}").json()["state"] == "placed"
    assert client.get(f"/agent/v1/requests/{req['id']}").json()["status"] == "ordered_alone"

    inbox = client.get("/api/inbox").json()
    assert [(i["id"], i["status"]) for i in inbox] == [(req["id"], "ordered_alone")]
    assert inbox[0]["sentence"].startswith("Ordered 1,000 × 1 l of lactose-free semi-skimmed milk for ")

    sp = client.get("/api/spend-passes/M-1").json()
    assert (sp["autoLimitCents"], sp["hardCapCents"], sp["diet"]) == (120000, 200000, ["lactose free"])
    assert "approvers" in sp["hidden"] and "approvers" not in sp["disclosed"]

    led = client.get("/api/ledger").json()
    assert led["chain"]["ok"] is True and led["chain"]["count"] == len(led["entries"])
    assert any(e["sentence"].startswith("Ordered 1,000 × 1 l of lactose-free semi-skimmed milk") and e["ruleIds"] == ["auto-order"]
               for e in led["entries"])
    assert any("Ignored the description of low-lactose whole milk 1 l" in e["sentence"] and "AI agents" in e["sentence"] for e in led["entries"])
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


def test_contradicted_choice_is_refused(client, holder):
    # the planted line asks for 463047; Validio rejected it for this need, so the agent cannot pick it
    req = ask_milk(client, holder)
    o = client.post("/agent/v1/orders", headers=auth(holder), json={
        "requestId": req["id"], "idempotencyKey": "planted", "choice": [{"productId": "463047", "salesQty": 132}]})
    assert o.status_code == 422
    assert "rejected" in o.json()["detail"] and "Low lactose is not lactose free" in o.json()["detail"]


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
            "/api/orders/{order_id}/reject", "/api/ledger", "/api/demo",
            "/api/demo/reset", "/api/health"} <= paths
    assert not {"/api/demo/stock-out", "/api/demo/ask", "/api/demo/example", "/api/agent/demo"} & paths
    assert "SupplyRequestView" in spec["components"]["schemas"]
    assert "liveChecked" in spec["components"]["schemas"]["SupplyRequestView"]["properties"]


def ask_mozzarella(client, holder):
    r = client.post("/agent/v1/requests", headers=auth(holder), json={
        "lines": [{"productId": "466375", "quantity": 200, "unit": "BAG"}], "deliverBy": "2026-11-16",
        "idempotencyKey": "mozz-1"})
    assert r.status_code == 200, r.text
    return r.json()


def test_demo_controls_answer_this_machine_and_nobody_else(client, monkeypatch):
    # the demo token is gone: the local kitchen's reset answers callers on this machine only, a demo copy's
    # reset its session (test_accounts)
    with TestClient(app, client=("203.0.113.7", 50000)) as remote:
        monkeypatch.setenv("VALIDIO_KITCHEN_TOKEN", "kt")
        assert remote.post("/api/demo/reset", headers={"X-Kitchen-Token": "kt", "X-Demo-Token": "x"}).status_code == 403
    monkeypatch.setenv("VALIDIO_DEMO", "")
    assert client.post("/api/demo/reset").status_code == 404
    monkeypatch.setenv("VALIDIO_DEMO", "1")
    assert client.get("/api/demo").json() == {"codeRequired": True, "stockOut466375": False, "realStock466375": {"quantity": 11603, "unit": "BAG"}, **VALIO}
    stockout()
    assert client.get("/api/demo").json()["stockOut466375"] is True


def test_no_shortcut_orders_or_stocks(client):
    # ordering only through an agent over MCP or the agent API; the stock-out has no switch
    for path in ("/api/demo/stock-out", "/api/demo/ask", "/api/demo/example", "/api/agent/demo",
                 "/api/demo/valio-down"):
        assert client.post(path, json={"text": "500 litres of lactose-free milk"}).status_code in (404, 405), path


def test_stockout_names_what_valio_really_has(client, holder, ctx):
    # read from Valio's (replayed) availability for the pass's delivery day, never a fixed number
    stockout()
    (entry,) = [e for e in client.get("/api/ledger").json()["entries"] if e["kind"] == "simulation"]
    assert entry["sentence"] == ("Simulated a stock-out of lactose-free mozzarella 125 g for the demo. "
                                 "Valio has 11,603 bags.")
    req = ask_mozzarella(client, holder)
    assert req["simulated"][0]["sentence"] == "Stock-out simulated for the demo. Valio has 11,603 bags."


def test_scene3_swap_waits_and_approve_needs_code(client, holder):
    stockout()
    req = ask_mozzarella(client, holder)
    assert req["status"] == "waiting" and req["decision"]["outcome"] == "ask_human"
    assert req["simulated"][0]["what"] == "stock-out of lactose-free mozzarella 125 g"
    assert req["liveChecked"]["ids"] <= 40
    subs = {o["productId"]: o["verdict"] for o in req["lines"][0]["substitutes"]}
    assert subs == {"466151": "blocked", "468526": "blocked", "475908": "blocked", "473986": "not_deliverable"}
    assert req["question"].endswith("?")
    oid = req["orderId"]
    assert client.post(f"/api/orders/{oid}/approve").status_code == 403
    assert client.post(f"/api/orders/{oid}/approve", json={"code": "000000"}).status_code == 403
    assert client.get(f"/api/orders/{oid}").json()["questionText"] == \
        "Order 10 × 2.5 kg of mozzarella-fontal crumbled cheese for 180.10 €?"
    r = client.post(f"/api/orders/{oid}/approve", headers={"X-Approve-Code": CODE})
    assert r.status_code == 200 and r.json()["state"] == "placed"
    assert [h["state"] for h in r.json()["history"]] == ["waiting", "approved", "placed"]
    assert client.post(f"/api/orders/{oid}/approve", json={"code": CODE}).status_code == 409
    assert client.get(f"/api/requests/{req['id']}").json()["status"] == "ordered"
    assert client.get("/api/ledger").json()["chain"]["ok"] is True


def test_wrong_codes_lock_the_order(client, holder):
    stockout()
    oid = ask_mozzarella(client, holder)["orderId"]
    for _ in range(5):
        assert client.post(f"/api/orders/{oid}/approve", json={"code": "111111"}).status_code == 403
    assert client.post(f"/api/orders/{oid}/approve", json={"code": CODE}).status_code == 429


def test_reject(client, holder):
    stockout()
    req = ask_mozzarella(client, holder)
    r = client.post(f"/api/orders/{req['orderId']}/reject", json={"code": CODE})
    assert r.json()["state"] == "rejected"
    assert client.get(f"/api/requests/{req['id']}").json()["status"] == "rejected"


def test_reset_starts_over(client, holder, ctx):
    ask_milk(client, holder)
    stockout()
    r = client.post("/api/demo/reset")
    assert r.json() == {"codeRequired": True, "stockOut466375": False, "realStock466375": {"quantity": 11603, "unit": "BAG"}, **VALIO}
    assert client.get("/api/inbox").json() == []
    assert client.get("/api/ledger").json()["chain"] == {"ok": True, "count": 0}
    assert ask_milk(client, holder)["id"] == "R-1"


def test_unknown_ids_are_404(client):
    assert client.get("/api/requests/R-99").status_code == 404
    assert client.get("/agent/v1/orders/O-99").status_code == 404
    # before any agent showed it, the page shows the pass as the kitchen issued it to the agent
    fresh = client.get("/api/spend-passes/M-1").json()
    assert (fresh["autoLimitCents"], fresh["hardCapCents"], fresh["usedCents"]) == (120000, 200000, 0)


def test_reader_failure_falls_back_with_ledger_note(client, holder, ctx, monkeypatch):
    """READER_MODE=modal without a URL: the fake reader answers and the ledger notes it once per product."""
    monkeypatch.setenv("READER_MODE", "modal")
    monkeypatch.delenv("MODAL_GEMMA_URL", raising=False)
    req = ask_milk(client, holder)
    st = {o["productId"]: o for o in req["lines"][0]["options"]}["463047"]["supplierText"]
    assert {"code": "addresses_agents", "text": "AI agents"} in st["reader"]["flags"]
    client.get(f"/api/requests/{req['id']}")
    notes = [e for e in client.get("/api/ledger").json()["entries"] if e["kind"] == "reader_fallback"]
    assert len(notes) == 1
    assert notes[0]["facts"] == [{"field": "product", "value": "463047"}]


def test_demo_says_whether_approve_needs_a_code(client, ctx):
    assert client.get("/api/demo").json()["codeRequired"] is True
    ctx.approve_code = ""
    assert client.get("/api/demo").json()["codeRequired"] is False


def test_spend_pass_shows_what_is_spent(client, holder):
    req = ask_milk(client, holder)
    assert client.get("/api/spend-passes/M-1").json()["usedCents"] == 0
    client.post("/agent/v1/orders", headers=auth(holder), json={
        "requestId": req["id"], "idempotencyKey": "milk-order-1",
        "choice": [{"productId": "464306", "salesQty": 1000, "priceCents": 101}]})
    assert client.get("/api/spend-passes/M-1").json()["usedCents"] == 101000


def _short(name):
    # about five words; a size like "5 × 1 l" is not a word, and no product number shows
    words = [w for w in name.split() if not re.fullmatch(r"[\d.,×x]+|[a-z]{1,2}", w)]
    return len(words) <= 6 and not re.search(r"\b4\d{5}\b", name)


def test_every_product_has_a_short_display_name(client, holder):
    req = ask_milk(client, holder)
    o = client.post("/agent/v1/orders", headers=auth(holder), json={
        "requestId": req["id"], "idempotencyKey": "milk-order-1",
        "choice": [{"productId": "464306", "salesQty": 1000, "priceCents": 101}]}).json()
    full = client.get(f"/api/requests/{req['id']}").json()
    opts = [p for ln in full["lines"] for p in ln["options"] + (ln.get("substitutes") or []) + (ln.get("beyondList") or [])]
    assert opts and all(_short(p["displayName"]) for p in opts), [p["displayName"] for p in opts]
    assert all(p["displayName"] == p["shortName"] and p["fullName"] for p in opts)
    lines = client.get(f"/api/orders/{o['id']}").json()["lines"]
    assert lines[0]["displayName"] == "Lactose-free semi-skimmed milk 1 l"


def test_request_and_order_show_what_the_pass_placed_before(client, holder):
    # O10: R-2 waits under Spend Pass M-1 after O-1 (milk, 1,010.00 €) was placed under it
    milk = ask_milk(client, holder)
    assert client.get(f"/api/requests/{milk['id']}").json()["usedBeforeCents"] == 0
    client.post("/agent/v1/orders", headers=auth(holder), json={
        "requestId": milk["id"], "idempotencyKey": "milk-order-1",
        "choice": [{"productId": "464306", "salesQty": 1000, "priceCents": 101}]})
    assert client.get(f"/api/requests/{milk['id']}").json()["usedBeforeCents"] == 0  # its own order is not before it
    stockout()
    mozz = ask_mozzarella(client, holder)
    assert mozz["id"] == "R-2"
    assert client.get("/api/requests/R-2").json()["usedBeforeCents"] == 101000
    assert client.get(f"/api/orders/{mozz['orderId']}").json()["usedBeforeCents"] == 101000
    assert client.get("/api/inbox").json()[0]["id"] == "R-2"


def test_options_carry_group_and_short_text(client, holder):
    # the page parses no text: turned-down options come with a heading and an order, every option a short line
    req = ask_milk(client, holder)
    opts = [o for ln in client.get(f"/api/requests/{req['id']}").json()["lines"] for o in ln["options"]]
    down = [o for o in opts if o["verdict"] in ("rejected", "blocked", "not_deliverable")]
    assert down and all(o["groupText"] and isinstance(o["groupOrder"], int) for o in down)
    assert not [o for o in opts if o not in down and "groupText" in o]
    groups = {o["groupText"]: o["groupOrder"] for o in down}
    assert {"Order cut-off passed", "Not lactose free", "Packs too small", "Not plain milk"} <= set(groups)
    assert all(groups[o["groupText"]] == o["groupOrder"] for o in down)  # one order per heading
    assert groups["Over the hard cap"] < groups["Not lactose free"] < groups["Order cut-off passed"]
    assert all(o["shortText"] and len(o["shortText"].split()) <= 9 for o in opts), [o["shortText"] for o in opts]
    by_rank = {o.get("rank"): o for o in opts}
    assert by_rank[1]["shortText"] == "Cheapest, always delivered in full."
    assert by_rank[2]["shortText"] == "+90.00 €"
    assert all(o["reasons"] for o in opts)


def test_ledger_entries_name_their_request(client, holder):
    milk = ask_milk(client, holder)
    client.post("/agent/v1/orders", headers=auth(holder), json={
        "requestId": milk["id"], "idempotencyKey": "milk-order-1",
        "choice": [{"productId": "464306", "salesQty": 1000, "priceCents": 101}]})
    stockout()
    ask_mozzarella(client, holder)
    got = [(e["kind"], e.get("requestId")) for e in client.get("/api/ledger").json()["entries"]]
    assert got[:4] == [("request", "R-1"), ("decision", "R-1"), ("decision", "R-1"), ("order", "R-1")]
    assert ("simulation", "demo") in got  # the stock-out is the demo's own group, not a request's
    assert all(r in ("R-1", "R-2", "demo") for _, r in got)
