"""Valio down in live mode: a timeout, a connection error or a 5xx is asked once more after a short pause
(both Valio endpoints only read, Validio never places an order at Valio), then the request is refused with
"Valio did not answer. Nothing was ordered." and one ledger entry. Nothing is placed."""

import re
from datetime import date

import httpx
import pytest
import respx
from asking import stockout
from test_api import MILK, auth, client, holder  # noqa: F401

from validio.api.state import get_ctx
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
    from conftest import CODE
    from test_api import ask_mozzarella
    stockout()
    oid = ask_mozzarella(client, holder)["orderId"]
    ctx.live.service.valio, _ = _down("5xx")
    r = client.post(f"/api/orders/{oid}/approve", headers={"X-Approve-Code": CODE})
    assert r.status_code == 503 and r.json()["detail"] == SAID
    assert client.get(f"/api/orders/{oid}").json()["state"] == "waiting"


def test_unrecorded_product_is_a_clean_503(client, holder):  # noqa: F811
    r = client.post("/agent/v1/requests", headers=auth(holder), json={
        "lines": [{"productId": "463361", "quantity": 10, "unit": "ST"}], "deliverBy": "2026-11-16",
        "idempotencyKey": "unrecorded-1"})
    assert r.status_code == 503, r.text
    detail = r.json()["detail"]
    assert detail.endswith("aren't recorded for this demo. Nothing was ordered.") and "463361" not in detail
    assert client.get("/api/inbox").json() == []


def test_a_schedule_line_without_a_date_is_no_delivery_date():
    """Valio's test API answers some products with one line of 0 and no availableDate."""
    from validio.valio.models import Availability

    a = Availability.from_api({"productId": "462556", "closingTime": "2026-11-15T17:00:00+0200", "salesBlock": False,
                               "logisticModel": "Stock",
                               "scheduleLines": [{"salesBlock": False, "availableAmount": 0.0, "salesUnit": "KG"}]},
                              "2026-11-14T00:01:02+0200")
    assert a.lines == [] and not a.deliverable


@pytest.mark.parametrize("status, cls, said", [(429, "ValioBusy", "Valio is busy"),
                                               (401, "ValioRefused", "refused Validio's key"),
                                               (403, "ValioRefused", "refused Validio's key")])
def test_busy_or_refused_key_is_valio_unavailable_not_a_500(status, cls, said):
    from validio.valio import client as vc

    with respx.mock(assert_all_called=False) as net:
        net.post(f"{OK}/api/price").mock(return_value=httpx.Response(status))
        c = ValioClient(OK, "key", "live", None, backoff=0)
        with pytest.raises(getattr(vc, cls), match=said) as e:
            c.price(["464306"], MONDAY, CallBudget())
        assert isinstance(e.value, ValioUnavailable) and len(net.calls) == 1


def test_valio_down_is_its_own_reason_and_a_retry_with_the_same_key_works(ctx, client, holder):  # noqa: F811
    """Valio down is not remembered under the idempotency key: once Valio answers, the same key gets a fresh
    request and exactly one order."""
    real = ctx.live.service.valio
    ctx.live.service.valio, _ = _down("5xx")
    body = {"lines": [{"text": MILK}], "deliverBy": "2026-11-16", "idempotencyKey": "down-retry"}
    first = client.post("/agent/v1/requests", headers=auth(holder), json=body).json()
    assert first["status"] == "blocked"
    d = first["decision"]
    assert d["reasonCode"] == "valio_down"
    assert re.fullmatch(r"Valio didn't answer at \d\d:\d\d\. Nothing was ordered\.", d["ownerText"]), d
    ctx.live.service.valio = real
    again = client.post("/agent/v1/requests", headers=auth(holder), json=body).json()
    assert again["id"] != first["id"] and again["decision"]["reasonCode"] != "valio_down"
    assert client.post("/agent/v1/requests", headers=auth(holder), json=body).json()["id"] == again["id"]
    assert client.get("/api/orders/O-1").status_code == 404  # the agent confirms nothing here, so no order


def test_simulated_valio_not_answering(client, holder):  # noqa: F811
    get_ctx().set_valio_down(True)  # no HTTP route, as with the stock-out: straight in the store
    state = client.get("/api/demo").json()
    assert state["valioDown"] is True and state["valioMode"] == "replay"
    assert state["valioModeText"] == "Valio's recorded answers"
    r = client.post("/agent/v1/requests", headers=auth(holder),
                    json={"lines": [{"text": MILK}], "deliverBy": "2026-11-16", "idempotencyKey": "sw-1"})
    assert r.json()["decision"]["reasonCode"] == "valio_down" and r.json()["decision"]["sentence"] == SAID
    get_ctx().set_valio_down(False)
    assert client.get("/api/demo").json()["valioDown"] is False
    r = client.post("/agent/v1/requests", headers=auth(holder),
                    json={"lines": [{"text": MILK}], "deliverBy": "2026-11-16", "idempotencyKey": "sw-1"})
    assert r.json()["decision"]["reasonCode"] == "auto_ok"
    sims = [e["sentence"] for e in client.get("/api/ledger").json()["entries"] if e["kind"] == "simulation"]
    assert sims[0].startswith("Simulated Valio not answering") and sims[1].startswith("Ended the simulated Valio")


def test_reset_turns_the_valio_switch_off(client):  # noqa: F811
    get_ctx().set_valio_down(True)
    assert client.post("/api/demo/reset").json()["valioDown"] is False
