"""Every status says why in one plain sentence (decision.reasonCode, decision.ownerText), each option carries
its comparison rows, and the request says how fast and from which Valio it was answered."""

import pytest
from asking import stockout
from test_api import MILK, ask_milk, ask_mozzarella, auth, client, holder  # noqa: F401

from validio.orders.explain import explain


@pytest.mark.parametrize("decision, status, code, text", [
    ({"outcome": "auto_order", "ruleIds": ["auto-order"],
      "sentence": "May order it automatically: 1,010.00 € is inside the auto limit of 1,200.00 € and every fact it needs "
                  "is attested."}, "ordered_alone", "auto_ok",
     "Bought without asking: 1,010.00 € is under your 1,200.00 € limit for automatic orders."),
    ({"outcome": "ask_human", "ruleIds": ["ask-human"],
      "sentence": "Needs a person: 1,390.00 € is over the auto limit of 1,200.00 €."}, "waiting", "over_alone",
     "Waiting for you: 1,390.00 € is over your 1,200.00 € limit for automatic orders."),
    ({"outcome": "block", "ruleIds": ["never-over-hard-cap"],
      "sentence": "Blocked: 2,194.00 € is over the hard cap of 2,000.00 €."}, "blocked", "hard_cap",
     "Not ordered: 2,194.00 € is over your 2,000.00 € never-above limit. Your buying agent can't change this."),
    ({"outcome": "block", "ruleIds": ["never-over-week-cap"],
      "sentence": "Blocked: Spend Pass M-1 already placed 7,000.00 € this week, this order of 1,113.00 € would "
                  "make 8,113.00 €, over the weekly limit of 8,000.00 €."}, "blocked", "week_cap",
     "Not ordered: this week would reach 8,113.00 €, over your 8,000.00 € weekly limit."),
    ({"outcome": "block", "ruleIds": ["never-break-diet"], "sentence": "Blocked: a diet rule ..."}, "blocked",
     "diet", "Not ordered: Valio's own data shows it isn't lactose free."),
    ({"outcome": "block", "ruleIds": [], "sentence": "Valio has no lactose-free parmesan. Nothing was ordered."},
     "blocked", "none_available", "Nothing suitable arrives by Mon 16 Nov. Nothing was ordered."),
    ({"outcome": "ask_human", "ruleIds": ["ask-human"],
      "sentence": "Needs a person: the substitute is not on Valio's list."}, "rejected", "swap_unlisted",
     "You chose not to order it. Nothing was ordered."),
])
def test_explain(decision, status, code, text):
    assert explain(decision, status, ["lactose free"], "2026-11-16") == {"reasonCode": code, "ownerText": text}


def test_auto_order_request_explains_itself_and_compares(client, holder):  # noqa: F811
    req = ask_milk(client, holder)
    v = client.get(f"/api/requests/{req['id']}").json()
    d = v["decision"]
    assert d["reasonCode"] == "auto_ok"
    assert d["ownerText"] == "Cleared to buy without asking: 1,010.00 € is under your 1,200.00 € limit for automatic orders."
    assert v["valioMode"] == "replay" and v["valioText"] == "Valio's recorded answers"
    assert isinstance(v["elapsedMs"], int) and v["speedText"].startswith("Done in ")
    assert f"{v['liveChecked']['ids']} products checked with Valio" in v["speedText"]
    line = v["lines"][0]
    assert line["decidedByText"].startswith(("Decided by: ", "Only one option fits"))
    chosen = next(o for o in line["options"] if o["verdict"] == "chosen")
    assert chosen["unitPriceText"] == "1.01 € per l"
    assert chosen["deliveryText"] == "Arrives Mon 16 Nov" and chosen["deliveryDate"] == "2026-11-16"
    assert chosen["reliabilityText"] and chosen["whyText"] and "whyNotText" not in chosen
    assert chosen["dietText"].startswith("Lactose free: Valio confirms")
    for o in line["options"]:
        if o["verdict"] != "chosen":
            assert o.get("whyNotText"), o
    assert d["sentence"]  # the old sentence stays next to the new text


def test_waiting_swap_explains_itself(client, holder):  # noqa: F811
    stockout()
    req = ask_mozzarella(client, holder)
    v = client.get(f"/api/requests/{req['id']}").json()
    assert v["status"] == "waiting"
    assert v["decision"]["ownerText"].startswith("Waiting for you: ")
    o = client.get(f"/api/orders/{req['orderId']}").json()
    assert o["decision"]["ownerText"] == v["decision"]["ownerText"]
    from conftest import CODE
    client.post(f"/api/orders/{req['orderId']}/approve", json={"code": CODE})
    v = client.get(f"/api/requests/{req['id']}").json()
    assert v["status"] == "ordered" and v["decision"]["ownerText"].startswith("Ordered after you approved")


def test_unreadable_request_says_so(client, holder):  # noqa: F811
    r = client.post("/agent/v1/requests", headers=auth(holder), json={
        "lines": [{"productId": "000000", "quantity": 1}], "deliverBy": "2026-11-16", "idempotencyKey": "bad-1"})
    d = r.json()["decision"]
    assert d["reasonCode"] == "unreadable" and d["ownerText"].endswith("Nothing was ordered.")
