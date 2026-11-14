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
    # by short name, the product ids stay in the orders the entries point to
    for name in ("300 × 1 l of lactose-free semi-skimmed milk", "137 × 125 g of parmesan reggiano",
                 "30 cartons of vegan pancake 30 g", "98 bags of lactose-free mozzarella 125 g"):
        assert name in sentences
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


def test_out_of_stock_drift_line_is_blocked_up_front(client):
    # O7: "Renew anyway" on a line Valio has none of was only ever refused. The renew line says both facts
    # at once and offers no button; the drift numbers stay for the sparkline
    seed.set_stockout(seed.db_path(), True)
    mozz = lines(client.post("/api/steady/S-1/renew", headers=CHEF).json())["466375"]
    assert mozz["result"] == "blocked" and "acceptLabel" not in mozz
    assert mozz["sentence"] == "Not renewed: none in stock at Valio. Also 26 % more per guest than usual."
    assert {f["kind"] for f in mozz["flags"]} >= {"per_guest_up", "stock_below"}
    assert mozz["history"]
    assert not any("Renew anyway" in f["sentence"] for f in mozz["flags"])
    log = AuditLog(seed.db_path())
    before = len(log.list())
    store = Store(seed.db_path())
    for _ in range(2):  # nothing to accept, nothing ordered, nothing logged
        assert client.post("/api/steady/S-1/lines/466375/accept", headers=CHEF).status_code == 409
    assert len(log.list()) == before
    assert not [o for o in store.orders() if o["lines"][0]["productId"] == "466375"]


def test_accepted_line_has_one_approval_tied_to_its_order(client):
    client.post("/api/steady/S-1/renew", headers=CHEF)
    log = AuditLog(seed.db_path())
    before = len(log.list())
    pan = lines(client.post("/api/steady/S-1/lines/471376/accept", headers=CHEF).json())["471376"]
    new = log.list()[before:]
    assert [e.kind for e in new if e.kind == "approval"] == ["approval"]
    assert {e.order_id for e in new} == {pan["orderId"]}


def test_order_after_an_accept_says_who_accepted(client):
    # the video showed "Ordered 27 cartons ... without a human" right after "Chef accepted 27 cartons"
    client.post("/api/steady/S-1/renew", headers=CHEF)
    log = AuditLog(seed.db_path())
    before = len(log.list())
    client.post("/api/steady/S-1/lines/471376/accept", headers=CHEF)
    orders = [e.sentence for e in log.list()[before:] if e.kind == "order"]
    assert len(orders) == 1
    assert "after the owner accepted" in orders[0]
    assert "without a" not in orders[0]
    assert "471376" not in orders[0]


def test_renewed_line_that_waits_is_ordered_once(client, monkeypatch):
    # review 3 M6 defect 1: Valio's second answer sends a renewed line to waiting with its own order O-x.
    # Accept made a second order and left O-x approvable too. Replay never gets there, so the answer is faked.
    from validio.orders.service import OrderService

    real = OrderService._decide

    def second_answer(self, mandate, quoted, *a, **kw):
        if quoted[0]["productId"] == "464306":
            return {"outcome": "ask_human", "ruleIds": [], "sentence": "Valio's second answer needs a person."}
        return real(self, mandate, quoted, *a, **kw)

    monkeypatch.setattr(OrderService, "_decide", second_answer)
    milk = lines(client.post("/api/steady/S-1/renew", headers=CHEF).json())["464306"]
    assert milk["result"] == "waiting" and milk["orderId"]
    monkeypatch.setattr(OrderService, "_decide", real)

    got = lines(client.post("/api/steady/S-1/lines/464306/accept", headers=CHEF).json())["464306"]
    store = Store(seed.db_path())
    assert got["result"] == "accepted" and got["orderId"] == milk["orderId"]
    assert store.order(milk["orderId"])["state"] == "placed"
    assert [o["id"] for o in store.orders() if o["lines"][0]["productId"] == "464306"] == [milk["orderId"]]


def test_order_the_split_orders_the_split_shown(client, monkeypatch):
    # review 3 M6 defect 2: a split that waits ("Order the split") was accepted as 177 of the short 463968
    from validio.policy.decide import Decision, Outcome
    from validio.standing import renew

    real = renew.decide_split
    monkeypatch.setattr(renew, "decide_split", lambda *a, **kw: Decision(Outcome.ESCALATE, [], "The split waits.", {}))
    parm = lines(client.post("/api/steady/S-1/renew", headers=CHEF).json())["463968"]
    assert (parm["result"], parm["acceptLabel"]) == ("waiting", "Order the split")
    shown = [(p["productId"], p["quantity"]) for p in parm["split"]["parts"]]
    assert shown == [("463968", 137), ("469648", 40)]
    monkeypatch.setattr(renew, "decide_split", real)

    got = lines(client.post("/api/steady/S-1/lines/463968/accept", headers=CHEF).json())["463968"]
    order = Store(seed.db_path()).order(got["orderId"])
    assert got["result"] == "accepted" and order["state"] == "placed"
    assert [(ln["productId"], ln["quantity"]) for ln in order["lines"]] == shown
    assert order["splitBaseCents"] == parm["split"]["totalCents"] - parm["split"]["extraCostCents"]


@pytest.mark.parametrize("second_answer_waits", [False, True])
def test_accept_writes_the_owner_approval_before_its_order(client, monkeypatch, second_answer_waits):
    # O5: the ledger reads cause, then effect. The person who accepts is the owner, as on every approve
    from validio.orders.service import OrderService

    real = OrderService._decide

    def decide(self, mandate, quoted, *a, **kw):
        if second_answer_waits:
            return {"outcome": "ask_human", "ruleIds": [], "sentence": "Valio's second answer needs a person."}
        return {**real(self, mandate, quoted, *a, **kw), "outcome": "auto_order"} \
            if quoted[0]["productId"] == "471376" else real(self, mandate, quoted, *a, **kw)

    client.post("/api/steady/S-1/renew", headers=CHEF)
    log = AuditLog(seed.db_path())
    before = len(log.list())
    monkeypatch.setattr(OrderService, "_decide", decide)
    client.post("/api/steady/S-1/lines/471376/accept", headers=CHEF)
    new = [e for e in log.list()[before:] if e.kind in ("approval", "order")]
    assert [e.kind for e in new] == ["approval", "order"], [(e.kind, e.sentence) for e in new]
    assert new[0].actor == "owner" and new[0].sentence.startswith("Owner accepted 27 cartons")
    assert log.verify().ok


def test_steady_ledger_entries_name_the_steady_order(client):
    client.post("/api/steady/S-1/renew", headers=CHEF)
    client.post("/api/steady/S-1/lines/471376/accept", headers=CHEF)
    entries = client.get("/api/ledger").json()["entries"]
    assert entries and {e.get("requestId") for e in entries} == {"S-1"}


def test_split_line_says_where_the_amount_comes_from(client):
    parm = lines(client.post("/api/steady/S-1/renew", headers=CHEF).json())["463968"]
    assert parm["sentence"].startswith("137 from this product, 40 from a swap.")
    assert "the usual line is" not in parm["sentence"]


def test_steady_orders_placed_alone_are_placed_by_validio(client):
    client.post("/api/steady/S-1/renew", headers=CHEF)
    alone = [e for e in client.get("/api/ledger").json()["entries"] if e["kind"] == "order"]
    assert alone and all(e["actor"] == "validio" for e in alone)
    assert alone[0]["displayText"].startswith("Placed O-")
    assert alone[0]["displayText"].endswith("for 303.00 € without asking you.")


def test_steady_short_texts(client):
    # D10, D11: one short line per held line, the long sentence stays for the fold and the ledger
    seed.set_stockout(seed.db_path(), True)
    got = lines(client.post("/api/steady/S-1/renew", headers=CHEF).json())
    assert got["466375"]["shortText"] == "None in stock at Valio."
    assert got["471376"]["shortText"] == "27 of 30 in stock."
    assert "shortText" not in got["464306"]
