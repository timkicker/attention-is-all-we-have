"""Play audit 3: a budget in the request text counts. Above it a person decides, and the sentence names it."""

from test_api import auth, client, holder  # noqa: F401


def ask(client, holder, text, key):  # noqa: F811
    r = client.post("/agent/v1/requests", headers=auth(holder),
                    json={"lines": [{"text": text}], "deliverBy": "2026-11-16", "idempotencyKey": key})
    assert r.status_code == 200, r.text
    return r.json()


def test_over_the_budget_needs_a_person(client, holder):  # noqa: F811
    req = ask(client, holder, "1000 litres of lactose-free milk by Monday, budget 500 euro", "low")
    d = req["decision"]
    assert req["status"] == "waiting" and d["outcome"] == "ask_human"
    assert "over-budget" in d["ruleIds"] and "auto-order" not in d["ruleIds"]
    assert "over the budget of 500.00 € the request names" in d["sentence"]
    assert "May order it alone" not in d["sentence"]
    order = client.get(f"/api/orders/{req['orderId']}").json()
    assert order["state"] == "waiting" and "budget of 500.00 €" in order["decision"]["sentence"]


def test_inside_the_budget_still_orders_alone(client, holder):  # noqa: F811
    req = ask(client, holder, "1000 litres of lactose-free milk by Monday, budget 1200 euro", "ok")
    assert req["decision"]["outcome"] == "auto_order"
    assert "budget" not in req["decision"]["sentence"]


def test_no_budget_changes_nothing(client, holder):  # noqa: F811
    req = ask(client, holder, "1000 litres of lactose-free milk by Monday", "none")
    assert req["decision"]["outcome"] == "auto_order"
