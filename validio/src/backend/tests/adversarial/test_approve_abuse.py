"""Abuse of the approve endpoint: double approve, approve after reject, two approves at once, wrong-code
lockout and a price that changes between the question and the approval (the re-check must fire)."""

import threading
from dataclasses import replace

import pytest
from conftest import CODE, TOKEN
from fastapi.testclient import TestClient

from validio.agent.holder import Holder
from validio.api.app import app
from validio.orders.service import ApproveRefused, OrderStateError


@pytest.fixture
def client(ctx):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def waiting(client, ctx):
    """Scene 3: the stock-out of 466375 sends a swap to the owner. Returns the waiting order id."""
    h = Holder.from_seed(lambda: client.get("/agent/v1/nonce").json()["nonce"], ctx.db_path, ctx.keys_dir)
    assert client.post("/api/demo/stock-out", headers={"X-Demo-Token": TOKEN}).status_code == 200
    r = client.post("/agent/v1/requests", headers={"Authorization": f"SD-JWT {h.presentation()}"}, json={
        "lines": [{"productId": "466375", "quantity": 200, "unit": "BAG"}], "deliverBy": "2026-11-16",
        "idempotencyKey": "mozz-abuse"})
    assert r.status_code == 200, r.text
    req = r.json()
    assert req["status"] == "waiting"
    return req["orderId"]


def approve(client, oid, code=CODE):
    return client.post(f"/api/orders/{oid}/approve", headers={"X-Approve-Code": code} if code else {})


def reject(client, oid, code=CODE):
    return client.post(f"/api/orders/{oid}/reject", json={"code": code})


def approvals(ctx, oid):
    return [e for e in ctx.audit.list(oid) if e.kind == "approval"]


def placed(ctx, oid):
    return [e for e in ctx.audit.list(oid) if e.kind == "order"]


def test_double_approve(client, ctx, waiting):
    assert approve(client, waiting).status_code == 200
    r = approve(client, waiting)
    assert r.status_code == 409 and "placed" in r.json()["detail"]
    assert len(approvals(ctx, waiting)) == 1 and len(placed(ctx, waiting)) == 1
    assert ctx.audit.verify().ok


def test_approve_after_reject_and_reject_after_approve(client, ctx, waiting):
    assert reject(client, waiting).json()["state"] == "rejected"
    r = approve(client, waiting)
    assert r.status_code == 409 and "rejected" in r.json()["detail"]
    assert client.get(f"/api/orders/{waiting}").json()["state"] == "rejected"
    assert placed(ctx, waiting) == []


def test_reject_after_approve(client, ctx, waiting):
    assert approve(client, waiting).status_code == 200
    assert reject(client, waiting).status_code == 409
    assert client.get(f"/api/orders/{waiting}").json()["state"] == "placed"


def test_placed_and_blocked_orders_cannot_be_approved(client, ctx):
    """An order placed alone or blocked by the Hard Lines never goes through approve."""
    h = Holder.from_seed(lambda: client.get("/agent/v1/nonce").json()["nonce"], ctx.db_path, ctx.keys_dir)
    auth = lambda: {"Authorization": f"SD-JWT {h.presentation()}"}
    for pid, qty, state in (("464306", 1000, "placed"), ("463047", 132, "blocked")):
        req = client.post("/agent/v1/requests", headers=auth(), json={
            "lines": [{"text": "1000 litres of lactose-free milk by Monday, budget 1200 euro"}],
            "deliverBy": "2026-11-16", "idempotencyKey": f"milk-{pid}"}).json()
        o = client.post("/agent/v1/orders", headers=auth(), json={
            "requestId": req["id"], "idempotencyKey": f"o-{pid}", "choice": [{"productId": pid, "salesQty": qty}]}).json()
        assert o["state"] == state
        assert approve(client, o["id"]).status_code == 409
        assert client.get(f"/api/orders/{o['id']}").json()["state"] == state


def test_two_approves_at_once_place_once(client, ctx, waiting):
    """Two phones press approve in the same instant: one order, one approval, one placed entry."""
    barrier, out = threading.Barrier(2), []

    def go():
        barrier.wait()
        try:
            out.append(ctx.orders.approve(waiting, approver="owner")["state"])
        except OrderStateError:
            out.append("409")

    threads = [threading.Thread(target=go) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(out) == ["409", "placed"]
    assert len(approvals(ctx, waiting)) == 1 and len(placed(ctx, waiting)) == 1
    assert ctx.audit.verify().ok


def test_approve_and_reject_at_once(client, ctx, waiting):
    barrier, out = threading.Barrier(2), []

    def go(fn):
        barrier.wait()
        try:
            out.append(fn(waiting, approver="owner")["state"])
        except OrderStateError:
            out.append("409")

    threads = [threading.Thread(target=go, args=(f,)) for f in (ctx.orders.approve, ctx.orders.reject)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(out) in (["409", "placed"], ["409", "rejected"])
    final = client.get(f"/api/orders/{waiting}").json()["state"]
    assert final in out and len(placed(ctx, waiting)) == (final == "placed")


def test_eight_http_approves_at_once(client, ctx, waiting):
    barrier, codes = threading.Barrier(8), []

    def go():
        barrier.wait()
        codes.append(approve(client, waiting).status_code)

    threads = [threading.Thread(target=go) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(codes) == [200] + [409] * 7
    assert len(placed(ctx, waiting)) == 1


# The 6 digit code

@pytest.mark.parametrize("code", ["", "000000", CODE[:-1], CODE + "0", f" {CODE}", f"{CODE}\n", "２４６８１０",
                                  CODE.encode().hex(), "' OR 1=1 --", CODE * 2])
def test_wrong_codes_are_refused(client, waiting, code):
    r = client.post(f"/api/orders/{waiting}/approve", json={"code": code})
    assert r.status_code == 403
    assert client.get(f"/api/orders/{waiting}").json()["state"] == "waiting"


def test_lockout_after_five_wrong_codes_holds_for_approve_and_reject(client, ctx, waiting):
    for i in range(5):
        fn = approve if i % 2 else reject
        assert fn(client, waiting, code="111111").status_code == 403
    assert approve(client, waiting).status_code == 429
    assert reject(client, waiting).status_code == 429
    assert client.get(f"/api/orders/{waiting}").json()["state"] == "waiting"


def test_header_wins_over_body(client, waiting):
    """A wrong header with the right code in the body is still a wrong code."""
    r = client.post(f"/api/orders/{waiting}/approve", headers={"X-Approve-Code": "999999"}, json={"code": CODE})
    assert r.status_code == 403


@pytest.mark.xfail(strict=True, reason="review-2 G10: the code is global but the lockout counts per order id, so "
                                       "unknown order ids give unlimited guesses and 404 vs 403 tells a right code")
def test_code_cannot_be_guessed_across_order_ids(client, waiting):
    guesses = [f"{n:06d}" for n in range(30) if f"{n:06d}" != CODE]
    for i, g in enumerate(guesses):
        assert approve(client, f"O-{9000 + i}", code=g).status_code in (403, 429)
    # an attacker learns nothing new from an unknown id with the right code ...
    assert approve(client, "O-9999", code=CODE).status_code in (403, 429)
    # ... and after 29 wrong guesses the right code no longer works anywhere
    assert approve(client, waiting).status_code == 429


def test_steady_accept_needs_the_code(client):
    """review-2 G11, fixed in 7681049: renew and accept place orders, so both need the code."""
    assert client.post("/api/steady/S-1/renew").status_code == 403
    assert client.post("/api/steady/S-1/renew", headers={"X-Approve-Code": CODE}).status_code == 200
    assert client.post("/api/steady/S-1/lines/471376/accept").status_code == 403
    assert client.post("/api/steady/S-1/lines/471376/accept", json={"code": "000000"}).status_code == 403
    r = client.post("/api/steady/S-1/lines/471376/accept", headers={"X-Approve-Code": CODE})
    assert r.status_code == 200, r.text


# The re-check from Valio between the question and the approval

class Repriced:
    """Valio's answer after the order started waiting: every price times `factor`, plus `add` cents."""

    def __init__(self, inner, factor=1.0, add=0, stock=None):
        self.inner, self.factor, self.add, self.stock = inner, factor, add, stock

    def price(self, *a, **kw):
        return {k: replace(q, price_cents=round(q.price_cents * self.factor) + self.add)
                if q.price_cents is not None else q for k, q in self.inner.price(*a, **kw).items()}

    def availability(self, *a, **kw):
        out = self.inner.availability(*a, **kw)
        if self.stock is None:
            return out
        return {k: replace(v, lines=[replace(ln, amount=self.stock) for ln in v.lines]) for k, v in out.items()}


def _reprice(ctx, **kw):
    spy = ctx.rt._valio
    spy.inner = Repriced(spy.inner, **kw)


def _price(client, oid):
    return [ln["priceCents"] for ln in client.get(f"/api/orders/{oid}").json()["lines"]]


@pytest.mark.parametrize("factor,add,ok", [
    (1.03, 0, False),   # 3 % up
    (1.0, 1, None),     # one cent up: allowed when within 2 %
    (1.02, 0, True),    # exactly 2 % is allowed
    (1.02, 1, False),   # one cent over 2 %
    (0.5, 0, True),     # cheaper is fine, the new total counts
    (10.0, 0, False),   # also past the hard cap
])
def test_price_change_before_approve(client, ctx, waiting, factor, add, ok):
    before = _price(client, waiting)
    _reprice(ctx, factor=factor, add=add)
    r = approve(client, waiting)
    if ok is None:
        ok = all((round(p * factor) + add) * 10000 <= p * 10200 for p in before)
    if ok:
        assert r.status_code == 200, r.text
        o = r.json()
        assert o["state"] == "placed"
        assert [ln["priceCents"] for ln in o["lines"]] == [round(p * factor) + add for p in before]
        assert o["totalCents"] == sum(ln["priceCents"] * ln["quantity"] for ln in o["lines"])
    else:
        assert r.status_code == 409, r.text
        assert r.json()["detail"].startswith("Approval refused, Valio was asked again")
        assert client.get(f"/api/orders/{waiting}").json()["state"] == "waiting"
        assert _price(client, waiting) == before, "a refused approval must not rewrite the order"
        assert any(e.sentence.startswith("Approval refused") for e in ctx.audit.list(waiting))
    assert ctx.audit.verify().ok


@pytest.mark.parametrize("stock", [0.0, 1.0])
def test_stock_gone_before_approve(client, ctx, waiting, stock):
    _reprice(ctx, stock=stock)
    r = approve(client, waiting)
    assert r.status_code == 409 and r.json()["detail"].startswith("Approval refused")
    assert client.get(f"/api/orders/{waiting}").json()["state"] == "waiting"


def test_refused_then_price_back_approves(client, ctx, waiting):
    """A refused approval leaves the order waiting; once Valio's price is back, the owner can approve."""
    spy = ctx.rt._valio
    honest = spy.inner
    _reprice(ctx, factor=1.5)
    assert approve(client, waiting).status_code == 409
    spy.inner = honest
    assert approve(client, waiting).json()["state"] == "placed"


def test_service_refuses_directly_too(ctx, waiting):
    _reprice(ctx, factor=1.05)
    with pytest.raises(ApproveRefused, match="more than 2 %"):
        ctx.orders.approve(waiting, approver="owner")


@pytest.mark.xfail(strict=True, reason="review-2 G12: approve does not check that the Spend Pass is still valid; "
                                       "a waiting order is placed after the pass expired")
def test_approve_after_the_spend_pass_expired(client, ctx, waiting, monkeypatch):
    monkeypatch.setenv("VALIDIO_NOW", "2026-11-17T00:00:01+02:00")  # M-1 ends 17 Nov 00:00
    r = approve(client, waiting)
    assert r.status_code == 409, r.text
