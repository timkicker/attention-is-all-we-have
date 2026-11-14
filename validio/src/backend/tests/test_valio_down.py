"""Valio down in live mode: a timeout, a connection error or a 5xx is asked once more after a short pause
(both Valio endpoints only read, Validio never places an order at Valio), then the request is refused with
"Valio did not answer. Nothing was ordered." and one ledger entry. Nothing is placed."""

from datetime import date

import httpx
import pytest
import respx
from test_api import MILK, auth, client, holder  # noqa: F401

from validio.valio.budget import CallBudget
from validio.valio.client import TEST_API_HOST, ValioClient, ValioUnavailable

OK = f"https://{TEST_API_HOST}"
MONDAY = date(2026, 11, 16)
SAID = "Valio did not answer. Nothing was ordered."
ERRORS = {
    "timeout": lambda req: (_ for _ in ()).throw(httpx.ReadTimeout("slow", request=req)),
    "connection": lambda req: (_ for _ in ()).throw(httpx.ConnectError("refused", request=req)),
    "5xx": lambda req: httpx.Response(503),
}


def _down(kind: str) -> tuple[ValioClient, list]:
    calls = []

    def handler(req):
        calls.append(req)
        return ERRORS[kind](req)
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return ValioClient(OK, "key", "live", None, http=http, backoff=0), calls


@pytest.mark.parametrize("kind", ERRORS)
def test_a_read_is_asked_once_more_then_refused(kind):
    c, calls = _down(kind)
    with pytest.raises(ValioUnavailable, match="Valio did not answer"):
        c.price(["464306"], MONDAY, CallBudget())
    assert len(calls) == 2


def test_a_second_try_that_works_is_used():
    with respx.mock(assert_all_called=False) as net:
        net.post(f"{OK}/api/price").mock(side_effect=[
            httpx.Response(502), httpx.Response(200, json={"products": [], "timeNow": "2026-11-14T10:00:00+0200"})])
        c = ValioClient(OK, "key", "live", None, backoff=0)
        assert c.price(["464306"], MONDAY, CallBudget()) == {}
        assert len(net.calls) == 2


def test_a_4xx_is_not_retried():
    with respx.mock(assert_all_called=False) as net:
        net.post(f"{OK}/api/price").mock(return_value=httpx.Response(422))
        c = ValioClient(OK, "key", "live", None, backoff=0)
        with pytest.raises(httpx.HTTPStatusError):
            c.price(["464306"], MONDAY, CallBudget())
        assert len(net.calls) == 1


@pytest.fixture(params=list(ERRORS))
def down(request, ctx):
    ctx.rt._valio, _ = _down(request.param)
    return request.param


def test_request_is_refused_and_nothing_placed(down, client, holder):  # noqa: F811
    r = client.post("/agent/v1/requests", headers=auth(holder),
                    json={"lines": [{"text": MILK}], "deliverBy": "2026-11-16", "idempotencyKey": "down-1"})
    assert r.status_code == 200, r.text
    req = r.json()
    assert req["status"] == "blocked"
    assert req["decision"]["outcome"] == "block"
    assert req["decision"]["sentence"] == SAID
    assert req.get("orderId") is None and client.get("/api/orders/O-1").status_code == 404
    said = [e for e in client.get("/api/ledger").json()["entries"] if e["sentence"] == SAID]
    assert len(said) == 1


def test_approve_while_valio_is_down_places_nothing(ctx, client, holder):  # noqa: F811
    from conftest import CODE, TOKEN
    from test_api import ask_mozzarella
    client.post("/api/demo/stock-out", headers={"X-Demo-Token": TOKEN})
    oid = ask_mozzarella(client, holder)["orderId"]
    ctx.live.service.valio, _ = _down("5xx")
    r = client.post(f"/api/orders/{oid}/approve", headers={"X-Approve-Code": CODE})
    assert r.status_code == 503 and r.json()["detail"] == SAID
    assert client.get(f"/api/orders/{oid}").json()["state"] == "waiting"


def test_unrecorded_product_is_a_clean_503(client, holder):  # noqa: F811
    r = client.post("/agent/v1/requests", headers=auth(holder), json={
        "lines": [{"productId": "463359", "quantity": 10, "unit": "ST"}], "deliverBy": "2026-11-16",
        "idempotencyKey": "unrecorded-1"})
    assert r.status_code == 503, r.text
    assert "no recorded" in r.json()["detail"]
    assert client.get("/api/inbox").json() == []
