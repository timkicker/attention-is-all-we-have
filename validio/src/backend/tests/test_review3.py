"""Review 3, orders/api/mcp: every finding as the test that failed before the fix (probes from tmp/rev3probe)."""

import threading
import time

import pytest
from conftest import CODE
from fastapi.testclient import TestClient
from test_api import ask_milk, ask_mozzarella, auth

from validio.agent.holder import Holder
from validio.api import tools
from validio.api.app import app

REMOTE = ("203.0.113.7", 50000)  # not loopback: what a public deploy sees


@pytest.fixture
def client(ctx):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def holder(client, ctx):
    return Holder.from_seed(lambda: client.get("/agent/v1/nonce").json(), ctx.db_path, ctx.keys_dir)


def mozz(client, holder, key):
    r = client.post("/agent/v1/requests", headers=auth(holder), json={
        "lines": [{"productId": "466375", "quantity": 200, "unit": "BAG"}], "deliverBy": "2026-11-16",
        "idempotencyKey": key})
    assert r.status_code == 200, r.text
    return r.json()


def entries(client):
    return client.get("/api/ledger").json()["entries"]


# H1: the approve code cannot be brute forced


def test_h1_unknown_order_gives_404_before_any_code_check(client, ctx):
    for i in range(8):
        assert client.post(f"/api/orders/NOPE-{i}/approve", json={"code": "000000"}).status_code == 404
    # the right code on an unknown id tells nothing either
    assert client.post("/api/orders/NOPE-99/approve", json={"code": CODE}).status_code == 404
    assert ctx.code_tries == {}


def test_h1_id_variants_are_unknown(client, holder):
    client.post("/api/demo/stock-out")
    oid = ask_mozzarella(client, holder)["orderId"]
    for _ in range(5):
        client.post(f"/api/orders/{oid}/approve", json={"code": "111111"})
    assert client.post(f"/api/orders/{oid} /approve", json={"code": "111111"}).status_code == 404
    assert client.post(f"/api/orders/{oid}/approve", json={"code": CODE}).status_code == 429


def test_h1_wrong_codes_count_per_client_across_orders(client, holder):
    client.post("/api/demo/stock-out")
    a, b = mozz(client, holder, "m-a")["orderId"], mozz(client, holder, "m-b")["orderId"]
    assert a != b
    for oid in (a, a, a, b, b):
        assert client.post(f"/api/orders/{oid}/approve", json={"code": "111111"}).status_code == 403
    # five wrong codes from this client: locked, even on an order with fewer tries and the right code
    assert client.post(f"/api/orders/{b}/approve", json={"code": CODE}).status_code == 429
    assert client.get(f"/api/orders/{b}").json()["state"] == "waiting"


# H3: approve checks the time again


@pytest.mark.parametrize("now, why", [("2026-11-15T18:00:00+02:00", "cut-off"),
                                      ("2026-11-17T01:00:00+02:00", "expired")])
def test_h3_approve_refuses_after_cutoff_or_expiry(client, holder, monkeypatch, now, why):
    client.post("/api/demo/stock-out")
    oid = ask_mozzarella(client, holder)["orderId"]
    monkeypatch.setenv("VALIDIO_NOW", now)
    r = client.post(f"/api/orders/{oid}/approve", json={"code": CODE})
    assert r.status_code == 409 and why in r.json()["detail"], r.text
    assert client.get(f"/api/orders/{oid}").json()["state"] == "waiting"
    refused = [e for e in entries(client) if e.get("orderId") == oid and e["kind"] == "decision"]
    assert why in refused[-1]["sentence"]
    assert not [e for e in entries(client) if e.get("orderId") == oid and e["kind"] == "order"]


def test_h3_placed_sentence_names_what_was_checked(client, holder):
    client.post("/api/demo/stock-out")
    oid = ask_mozzarella(client, holder)["orderId"]
    client.post(f"/api/orders/{oid}/approve", json={"code": CODE})
    (s,) = [e["sentence"] for e in entries(client) if e.get("orderId") == oid and e["kind"] == "order"]
    assert "after the owner approved" in s and "16 Nov" in s and "cut-off" in s and "without a human" not in s


# H5: one request, at most one order


def test_h5_concurrent_confirms_place_one_order(client, holder, ctx):
    req = ask_milk(client, holder)
    mandates = [ctx.verify(holder.presentation()) for _ in range(16)]
    got, errors = [], []
    start = threading.Barrier(16)

    def confirm(i):
        start.wait()
        try:
            got.append(ctx.supply.confirm_order(mandate=mandates[i], request_id=req["id"],
                                                choice=[("464306", 1000)], idempotency_key=f"c-{i}")["id"])
        except Exception as e:  # noqa: BLE001
            errors.append(repr(e))

    ts = [threading.Thread(target=confirm, args=(i,)) for i in range(16)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert errors == [] and set(got) == {"O-1"}
    assert len(ctx.store.orders()) == 1
    assert len([e for e in entries(client) if e["kind"] == "order"]) == 1


def test_h5_store_refuses_a_second_order_for_a_request(ctx):
    import sqlite3

    ctx.store.new_order({"requestId": "R-1", "state": "placed"})
    with pytest.raises(sqlite3.IntegrityError):
        ctx.store.new_order({"requestId": "R-1", "state": "placed"})
    ctx.store.new_order({"requestId": None, "state": "placed"})
    ctx.store.new_order({"requestId": None, "state": "placed"})  # Steady Orders carry no request


# M2: only options Validio accepted for this need


def test_m2_rejected_option_cannot_be_confirmed(client, holder):
    req = ask_milk(client, holder)
    opts = {o["productId"]: o["verdict"] for o in req["lines"][0]["options"]}
    assert opts["463779"] == "rejected"
    r = client.post("/agent/v1/orders", headers=auth(holder), json={
        "requestId": req["id"], "idempotencyKey": "small", "choice": [{"productId": "463779", "salesQty": 100}]})
    assert r.status_code == 422 and "rejected" in r.json()["detail"]
    assert client.get("/api/inbox").json()[0]["status"] == "working"


def test_m2_duplicate_products_refused(client, holder):
    req = ask_milk(client, holder)
    r = client.post("/agent/v1/orders", headers=auth(holder), json={
        "requestId": req["id"], "idempotencyKey": "dup",
        "choice": [{"productId": "464306", "salesQty": 500}, {"productId": "464306", "salesQty": 500}]})
    assert r.status_code == 422 and "twice" in r.json()["detail"]


# M3: a failed request is blocked, logged and idempotent


def test_m3_failed_request_is_blocked_with_a_decision(client, holder):
    body = {"lines": [{"text": "1000 litres of lactose-free milk"}, {"text": "50 kg of unobtainium"}],
            "deliverBy": "2026-11-16", "idempotencyKey": "unobtainium"}
    r = client.post("/agent/v1/requests", headers=auth(holder), json=body)
    assert r.status_code == 200, r.text
    req = r.json()
    assert req["status"] == "blocked" and req["decision"]["outcome"] == "block"
    assert "no known product kind" in req["decision"]["sentence"]
    again = client.post("/agent/v1/requests", headers=auth(holder), json=body).json()
    assert again["id"] == req["id"]
    assert len(client.get("/api/inbox").json()) == 1
    asked = [e for e in entries(client) if e["kind"] == "request"]
    refused = [e for e in entries(client) if e["kind"] == "decision" and "no known product kind" in e["sentence"]]
    assert len(asked) == 1 and len(refused) == 1
    # nothing to confirm, and a readable answer
    c = client.post("/agent/v1/orders", headers=auth(holder), json={
        "requestId": req["id"], "idempotencyKey": "x", "choice": [{"productId": "464306", "salesQty": 1}]})
    assert c.status_code == 422 and "blocked" in c.json()["detail"]


def test_m3_internal_keyerror_is_not_a_404(ctx, monkeypatch):
    def boom(*_a, **_k):
        raise KeyError("lines")

    monkeypatch.setattr(tools, "get_request", boom)
    with TestClient(app, raise_server_exceptions=False) as c:
        assert c.get("/agent/v1/requests/R-1").status_code == 500
        assert c.get("/agent/v1/orders/O-404").status_code == 404


# M4: a request key belongs to one body


def test_m4_request_key_with_another_body_conflicts(client, holder):
    ask_milk(client, holder, key="same")
    r = client.post("/agent/v1/requests", headers=auth(holder), json={
        "lines": [{"text": "10 bags of lactose-free mozzarella"}], "deliverBy": "2026-11-16",
        "idempotencyKey": "same"})
    assert r.status_code == 409


# M7: reset waits for writes, order and ledger move together


class Slow:
    def __init__(self, inner, delay):
        self.inner, self.delay = inner, delay

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def price(self, *a, **k):
        time.sleep(self.delay)
        return self.inner.price(*a, **k)


def test_m7_reset_during_approve_is_clean(client, holder, ctx):
    client.post("/api/demo/stock-out")
    oid = ask_mozzarella(client, holder)["orderId"]
    ctx.orders.valio = Slow(ctx.orders.valio, 0.5)
    out = {}

    def approve():
        try:
            out["order"] = ctx.orders.approve(oid, "owner")["state"]
        except Exception as e:  # noqa: BLE001
            out["error"] = repr(e)

    t = threading.Thread(target=approve)
    t.start()
    time.sleep(0.1)
    ctx.reset()
    t.join()
    assert out == {"order": "placed"}, out  # the reset waited
    assert ctx.store.orders() == [] and ctx.audit.verify().ok and ctx.audit.verify().count == 0


def test_m7_order_and_ledger_entry_are_one_write(client, holder, ctx, monkeypatch):
    client.post("/api/demo/stock-out")
    oid = ask_mozzarella(client, holder)["orderId"]
    before = ctx.audit.verify().count
    real = ctx.audit.append

    def fail_on_order(**kw):
        if kw["kind"] == "order":
            raise RuntimeError("disk full")
        return real(**kw)

    with monkeypatch.context() as m, pytest.raises(RuntimeError):
        m.setattr(ctx.audit, "append", fail_on_order)
        ctx.orders.approve(oid, "owner")
    assert ctx.orders.get(oid)["state"] == "waiting"
    assert ctx.audit.verify().count == before and ctx.audit.verify().ok


# M8: closed by default when not local


def test_m8_demo_is_off_by_default(monkeypatch):
    from validio.config import load_settings

    monkeypatch.delenv("VALIDIO_DEMO", raising=False)
    assert load_settings(env_file=None).demo is False


def test_m8_remote_approve_and_demo_closed_without_code_and_token(ctx, holder, monkeypatch):
    with TestClient(app) as local:
        local.post("/api/demo/stock-out")
        oid = ask_mozzarella(local, holder)["orderId"]
    monkeypatch.setenv("VALIDIO_KITCHEN_TOKEN", "kt")
    ctx.approve_code = ""
    with TestClient(app, client=REMOTE, headers={"X-Kitchen-Token": "kt"}) as remote:
        assert remote.post(f"/api/orders/{oid}/approve").status_code == 403
        assert remote.post("/api/demo/reset").status_code == 403
        assert remote.get(f"/api/orders/{oid}").json()["state"] == "waiting"


def test_m8_public_mode_refuses_to_start_without_secrets(ctx, monkeypatch):
    monkeypatch.setenv("VALIDIO_PUBLIC", "1")
    monkeypatch.setenv("VALIDIO_KITCHEN_TOKEN", "")
    with pytest.raises(RuntimeError, match="VALIDIO_KITCHEN_TOKEN"), TestClient(app):
        pass


# M9: reads behind a kitchen token for anyone not on this machine


def test_m9_remote_reads_need_the_kitchen_token(ctx, monkeypatch):
    monkeypatch.delenv("VALIDIO_KITCHEN_TOKEN", raising=False)
    with TestClient(app, client=REMOTE) as remote:
        for path in ("/api/inbox", "/api/ledger", "/api/orders/O-1", "/api/steady", "/api/demo"):
            assert remote.get(path).status_code == 403, path  # no token configured: closed
        assert remote.get("/api/health").status_code == 200
    monkeypatch.setenv("VALIDIO_KITCHEN_TOKEN", "kt-secret")
    with TestClient(app, client=REMOTE) as remote:
        assert remote.get("/api/inbox").status_code == 401
        assert remote.get("/api/inbox", headers={"X-Kitchen-Token": "nope"}).status_code == 401
        assert remote.get("/api/inbox", headers={"X-Kitchen-Token": "kt-secret"}).status_code == 200
        assert remote.post("/api/session", json={"token": "nope"}).status_code == 401
        assert remote.post("/api/session", json={"token": "kt-secret"}).status_code == 204
        assert remote.get("/api/ledger").status_code == 200  # the cookie
    with TestClient(app) as local:
        assert local.get("/api/inbox").status_code == 200  # this machine needs no token


# L1: MCP host allow-list


def test_l1_mcp_host_allow_list_is_configurable(ctx, monkeypatch):
    hdr = {"Host": "validio-demo.modal.run", "Accept": "application/json, text/event-stream",
           "Content-Type": "application/json"}
    init = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}}
    with TestClient(app) as c:
        assert c.post("/mcp/", headers=hdr, json=init).status_code == 421
    monkeypatch.setenv("VALIDIO_MCP_HOSTS", "validio-demo.modal.run")
    with TestClient(app) as c:
        assert c.post("/mcp/", headers=hdr, json=init).status_code == 200


# M1: Steady Orders run on their own weekly Spend Pass, so the agent's orders under M-1 do not eat its limits

def test_m1_steady_order_has_its_own_weekly_pass(client, holder, ctx):
    from validio.demo.seed import STEADY_PASS_ID

    req = ask_milk(client, holder)
    o = client.post("/agent/v1/orders", headers=auth(holder), json={
        "requestId": req["id"], "idempotencyKey": "m1", "choice": [{"productId": "464306", "salesQty": 1000}]})
    assert o.json()["state"] == "placed" and o.json()["spendPassId"] == "M-1"
    view = client.post("/api/steady/S-1/renew", headers={"X-Approve-Code": CODE}).json()
    got = {ln["productId"]: ln for ln in view["lines"]}
    assert (got["464306"]["result"], got["464306"]["totalCents"]) == ("renewed", 30300)
    assert (got["463968"]["result"], got["463968"]["thisWeekQuantity"], got["463968"]["totalCents"]) == \
        ("split_renewed", 177, 77249)
    for pid in ("464306", "463968"):
        assert ctx.orders.get(got[pid]["orderId"])["spendPassId"] == STEADY_PASS_ID
    sp = client.get("/api/steady/S-1").json()["steadyPass"]
    assert sp == {"id": STEADY_PASS_ID, "validFrom": "2026-11-09T00:00:00+02:00",
                  "validTo": "2026-11-16T00:00:00+02:00", "autoLimitCents": 120000, "hardCapCents": 200000,
                  "usedCents": 30300 + 77249}
