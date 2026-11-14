"""An agent's request, confirm and the owner's approve end to end over HTTP, on the synthetic set (no Valio data)."""

import threading

import pytest
from conftest import CODE
from fastapi.testclient import TestClient

from validio.agent.holder import Holder
from validio.api.app import app

MILK = "litres of lactose-free milk by Monday"


@pytest.fixture
def c(syn_ctx):
    with TestClient(app) as client:
        yield client


@pytest.fixture
def holder(c, syn_ctx):
    return Holder.from_seed(lambda: c.get("/agent/v1/nonce").json(), syn_ctx.db_path, syn_ctx.keys_dir)


def ask(c, holder, litres, key):
    r = c.post("/agent/v1/requests", headers={"Authorization": f"SD-JWT {holder.presentation()}"},
               json={"lines": [{"text": f"{litres} {MILK}"}], "deliverBy": "2026-11-16", "idempotencyKey": key})
    assert r.status_code == 200, r.text
    return r.json()


def confirm(c, holder, req, key):
    choice = [{"productId": ln["chosen"]["productId"], "salesQty": ln["chosen"]["salesQty"]} for ln in req["lines"]]
    return c.post("/agent/v1/orders", headers={"Authorization": f"SD-JWT {holder.presentation()}"},
                  json={"requestId": req["requestId"], "choice": choice, "idempotencyKey": key})


def test_order_alone_inside_the_auto_limit(c, holder):
    req = ask(c, holder, 100, "k1")
    assert req["decision"]["outcome"] == "auto_order"
    o = confirm(c, holder, req, "c1")
    assert o.status_code == 200 and o.json()["state"] == "placed" and o.json()["totalCents"] == 10000
    again = confirm(c, holder, req, "c1")  # a retry gives the same order
    assert again.json()["id"] == o.json()["id"]


def test_retry_with_the_same_key_gives_the_same_request(c, holder):
    a, b = ask(c, holder, 100, "same"), ask(c, holder, 100, "same")
    assert a["requestId"] == b["requestId"]
    r = c.post("/agent/v1/requests", headers={"Authorization": f"SD-JWT {holder.presentation()}"},
               json={"lines": [{"text": f"200 {MILK}"}], "deliverBy": "2026-11-16", "idempotencyKey": "same"})
    assert r.status_code == 409


def test_over_the_auto_limit_waits_and_the_owner_approves(c, holder):
    req = ask(c, holder, 1500, "k2")
    assert req["decision"]["outcome"] == "ask_human" and req["status"] == "waiting"
    oid = req["orderId"]
    assert c.post(f"/api/orders/{oid}/approve", headers={"X-Approve-Code": CODE}).json()["state"] == "placed"
    assert c.post(f"/api/orders/{oid}/approve", headers={"X-Approve-Code": CODE}).status_code == 409


def test_over_the_hard_cap_is_blocked(c, holder):
    req = ask(c, holder, 2500, "k3")
    assert req["decision"]["outcome"] == "block" and req["status"] == "blocked"


def test_parallel_confirms_place_one_order(c, holder, syn_ctx):
    req = ask(c, holder, 100, "k4")
    presentations = [holder.presentation() for _ in range(4)]
    out = []

    def go(i):
        choice = [{"productId": ln["chosen"]["productId"], "salesQty": ln["chosen"]["salesQty"]} for ln in req["lines"]]
        out.append(c.post("/agent/v1/orders", headers={"Authorization": f"SD-JWT {presentations[i]}"},
                          json={"requestId": req["requestId"], "choice": choice, "idempotencyKey": f"p{i}"}))

    ts = [threading.Thread(target=go, args=(i,)) for i in range(4)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert all(r.status_code == 200 for r in out), [r.text for r in out]
    assert len({r.json()["id"] for r in out}) == 1
    assert sum(1 for o in syn_ctx.store.orders() if o.get("requestId") == req["requestId"]) == 1
    assert syn_ctx.audit.verify().ok


def test_a_slow_valio_never_holds_the_kitchen_lock(c, holder, syn_ctx, monkeypatch):
    import time

    spy = syn_ctx.rt._valio
    inner = spy.price
    asking = threading.Event()

    def slow_price(*a, **kw):
        asking.set()
        time.sleep(1.0)
        return inner(*a, **kw)

    monkeypatch.setattr(spy, "price", slow_price)
    t = threading.Thread(target=ask, args=(c, holder, 100, "slow"))
    t.start()
    assert asking.wait(5)
    got = syn_ctx.orders.lock.acquire(timeout=0.3)  # while Valio is being asked
    assert got, "the kitchen's lock was held while Valio was asked"
    syn_ctx.orders.lock.release()
    t.join()


def test_an_error_before_any_decision_leaves_no_request_and_frees_the_key(c, holder, syn_ctx):
    entries = len(syn_ctx.audit.list())
    r = c.post("/agent/v1/requests", headers={"Authorization": f"SD-JWT {holder.presentation()}"},
               json={"lines": [{"text": f"100 {MILK}"}], "deliverBy": "2026-11-20", "idempotencyKey": "no-day"})
    assert r.status_code == 503  # no recorded answers for that day
    assert len(syn_ctx.audit.list()) == entries and syn_ctx.store.requests() == []
    assert ask(c, holder, 100, "no-day")["decision"]["outcome"] == "auto_order"  # the key is free again
    assert syn_ctx.audit.verify().ok


def test_cached_request_views_follow_every_write(c, holder):
    req = ask(c, holder, 1500, "cache")
    rid, oid = req["requestId"], req["orderId"]
    assert c.get(f"/api/requests/{rid}").json()["status"] == "waiting"
    assert c.get(f"/api/requests/{rid}").json()["status"] == "waiting"  # served from the cache
    inbox = c.get("/api/inbox").json()
    assert any(i["id"] == rid and i["status"] == "waiting" for i in inbox)
    c.post(f"/api/orders/{oid}/approve", headers={"X-Approve-Code": CODE})
    assert c.get(f"/api/requests/{rid}").json()["status"] == "ordered"
    assert any(i["id"] == rid and i["status"] == "ordered" for i in c.get("/api/inbox").json())
    # a caller trimming its copy never changes what the next caller gets
    from validio.api.tools import get_request

    a = get_request(_ctx(), rid)
    a.lines[0].options.clear()
    assert get_request(_ctx(), rid).lines[0].options


def _ctx():
    from validio.api.state import get_ctx

    return get_ctx()
