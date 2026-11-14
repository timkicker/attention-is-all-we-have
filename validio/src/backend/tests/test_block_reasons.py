"""Rerun 5: a turned-down row names the rule it breaks, and a line with no product at all says so plainly."""

from test_api import client  # noqa: F401

from validio.api.display import group, short_text


def ask(client, text):  # noqa: F811
    j = client.post("/api/demo/ask", json={"text": text}).json()
    return client.get(f"/api/requests/{j['requestId']}").json()


def test_outside_the_product_groups_is_named():
    r = ["Cheapest safe option.", "Blocked: it is outside the Spend Pass's product groups."]
    assert group(r)[0] == "Outside the pass's product groups"
    assert short_text("blocked", r) == "Outside the pass's product groups."


def test_butter_rows_name_their_rule(client):  # noqa: F811
    req = ask(client, "50 kg of butter by Monday")
    heads = {o["shortText"] for ln in req["lines"] for o in ln["options"] if o["verdict"] == "blocked"}
    assert heads and "Breaks a Spend Pass rule." not in heads, heads


def test_no_lactose_free_parmesan_is_one_plain_reason(client):  # noqa: F811
    req = ask(client, "20 kg of parmesan by Monday")
    assert req["status"] == "blocked"
    assert req["decision"]["sentence"] == "Valio has no lactose-free parmesan. Nothing was ordered."
