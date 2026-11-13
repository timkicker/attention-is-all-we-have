"""Scene 4 over HTTP, end to end from a reset, twice in a row.

Renew: milk 464306 renewed alone (300, 303.00 EUR), parmesan split 177 for 772.49 EUR (2.5 % more), pancakes
471376 wait (27 of 30), mozzarella 466375 flagged 26 % more per guest. Accept the pancakes: the order is placed
and the ledger verifies. Numbers from the blueprint, scene 4."""

import pytest
from fastapi.testclient import TestClient

from validio.audit.log import AuditLog
from validio.config import load_settings
from validio.demo import seed
from validio.orders.store import Store

CODE = "135790"
CHEF = {"X-Approve-Code": CODE}  # renew and accept place orders: the same code as approve (review 3 H2)


@pytest.fixture
def client(tmp_path, monkeypatch, catalog):
    s = load_settings()
    if not any(s.valio_cache.glob("price/*/*.json")):
        pytest.skip("needs_data: no recorded Valio answers, run make record")
    monkeypatch.setenv("VALIDIO_DB", str(tmp_path / "validio.db"))
    monkeypatch.setenv("VALIDIO_KEYS", str(tmp_path / "keys"))
    monkeypatch.setenv("VALIDIO_APPROVE_CODE", CODE)
    seed.reset()
    from validio.api.app import app
    from validio.api.state import set_ctx

    set_ctx(None)  # a fresh Ctx reads the code above
    with TestClient(app) as c:
        yield c
    set_ctx(None)


def lines(body):
    return {ln["productId"]: ln for ln in body["lines"]}


def scene4(client):
    (summary,) = client.get("/api/steady").json()
    assert (summary["id"], summary["lineCount"], summary["weekday"]) == ("S-1", 4, "Monday")

    before = client.get("/api/steady/S-1").json()
    assert before["simulatedHistory"] is True and before["guestsPerWeek"] == 400 and before["weeksLearned"] == 8
    assert {ln["result"] for ln in before["lines"]} == {"pending"}
    assert lines(before)["466375"]["usualQuantity"] == 98
    assert lines(before)["466375"]["history"] == [92, 92, 94, 96, 100, 108, 116, 120]

    r = client.post("/api/steady/S-1/renew", headers=CHEF)
    assert r.status_code == 200
    got = lines(r.json())
    milk, parm, pan, mozz = got["464306"], got["463968"], got["471376"], got["466375"]
    assert (milk["result"], milk["thisWeekQuantity"], milk["totalCents"]) == ("renewed", 300, 30300)
    assert (parm["result"], parm["thisWeekQuantity"], parm["totalCents"]) == ("split_renewed", 177, 77249)
    assert parm["split"]["extraCostPct"] == 2.5 and parm["split"]["extraCostCents"] == 1849
    assert [(p["productId"], p["quantity"], p["onValioList"]) for p in parm["split"]["parts"]] == \
        [("463968", 137, False), ("469648", 40, True)]
    assert (pan["result"], pan["thisWeekQuantity"], pan["acceptLabel"]) == ("waiting", 27, "Order 27 now")
    assert "wheat" in pan["sentence"]
    assert mozz["result"] == "flagged"
    assert [(f["kind"], f["pct"]) for f in mozz["flags"]] == [("per_guest_up", 26)]
    assert r.json()["renewedAt"]

    store = Store(seed.db_path())
    assert store.order(milk["orderId"])["state"] == "placed"
    assert store.order(parm["orderId"])["state"] == "placed"
    assert "orderId" not in pan and "orderId" not in mozz

    again = client.post("/api/steady/S-1/renew", headers=CHEF).json()  # a second press orders nothing twice
    assert lines(again)["464306"]["orderId"] == milk["orderId"]
    assert len(store.orders()) == 2

    a = client.post("/api/steady/S-1/lines/471376/accept", headers=CHEF)
    assert a.status_code == 200
    pan = lines(a.json())["471376"]
    assert pan["result"] == "accepted"
    order = store.order(pan["orderId"])
    assert order["state"] == "placed"
    assert [(ln["productId"], ln["quantity"]) for ln in order["lines"]] == [("471376", 27)]

    assert client.post("/api/steady/S-1/lines/464306/accept", headers=CHEF).status_code == 409
    assert client.post("/api/steady/S-1/lines/999/accept", headers=CHEF).status_code == 404

    v = AuditLog(seed.db_path()).verify()
    assert v.ok and v.count >= 6
    return [ln["orderId"] for ln in (milk, parm, pan)]


def test_scene4_end_to_end_twice_from_a_reset(client):
    first = scene4(client)
    seed.reset()  # `make seed` while the server runs: the stores reopen
    second = scene4(client)
    assert first == second == ["O-1", "O-2", "O-3"]


def test_unknown_steady_order_is_404(client):
    assert client.get("/api/steady/S-9").status_code == 404
    assert client.post("/api/steady/S-9/renew", headers=CHEF).status_code == 404


def test_accept_before_renew_is_409(client):
    assert client.post("/api/steady/S-1/lines/471376/accept", headers=CHEF).status_code == 409


def test_ledger_names_every_line_decision(client):
    client.post("/api/steady/S-1/renew", headers=CHEF)
    sentences = " ".join(e.sentence for e in AuditLog(seed.db_path()).list())
    for pid in ("464306", "463968", "471376", "466375"):
        assert pid in sentences
    assert "26 % more per guest" in sentences


def test_renew_and_accept_need_the_approve_code(client):
    # review 3 H2 probe: renew and accept without a code placed orders O-1 to O-3
    assert client.post("/api/steady/S-1/renew").status_code == 403
    assert client.post("/api/steady/S-1/renew", headers={"X-Approve-Code": "000000"}).status_code == 403
    store = Store(seed.db_path())
    assert store.orders() == [] and client.get("/api/steady/S-1").json()["lines"][0]["result"] == "pending"

    assert client.post("/api/steady/S-1/renew", json={"code": CODE}).status_code == 200  # body works like approve
    assert client.post("/api/steady/S-1/lines/471376/accept").status_code == 403
    assert client.post("/api/steady/S-1/lines/471376/accept", json={"code": "000000"}).status_code == 403
    assert lines(client.get("/api/steady/S-1").json())["471376"]["result"] == "waiting"
    assert len(store.orders()) == 2


def test_refused_accept_leaves_one_decision_and_no_hidden_order(client):
    # review 3 M5 probe: stock-out, renew, accept the mozzarella three times. Each try wrote "Chef accepted"
    # with no order id before anything was decided, and O-3 stayed waiting where no page showed it
    seed.set_stockout(seed.db_path(), True)
    client.post("/api/steady/S-1/renew", headers=CHEF)
    log = AuditLog(seed.db_path())
    before = len(log.list())
    r = client.post("/api/steady/S-1/lines/466375/accept", headers=CHEF)
    assert r.status_code == 409 and "Approval refused" in r.json()["detail"]
    after_first = log.list()[before:]
    assert all(e.order_id for e in after_first)
    assert not [e for e in after_first if e.actor == "kitchen:chef"]  # the chef's acceptance never came true
    store = Store(seed.db_path())
    assert [o["state"] for o in store.orders() if o["lines"][0]["productId"] == "466375"] == ["rejected"]
    mozz = lines(client.get("/api/steady/S-1").json())["466375"]
    assert mozz["result"] == "blocked" and "Approval refused" in mozz["sentence"] and "acceptLabel" not in mozz

    for _ in range(2):  # a retry decides nothing new
        assert client.post("/api/steady/S-1/lines/466375/accept", headers=CHEF).status_code == 409
    assert len(log.list()) == before + len(after_first)
    assert not [o for o in store.orders() if o["state"] == "waiting"]


def test_accepted_line_has_one_approval_tied_to_its_order(client):
    client.post("/api/steady/S-1/renew", headers=CHEF)
    log = AuditLog(seed.db_path())
    before = len(log.list())
    pan = lines(client.post("/api/steady/S-1/lines/471376/accept", headers=CHEF).json())["471376"]
    new = log.list()[before:]
    assert [e.kind for e in new if e.kind == "approval"] == ["approval"]
    assert {e.order_id for e in new} == {pan["orderId"]}
