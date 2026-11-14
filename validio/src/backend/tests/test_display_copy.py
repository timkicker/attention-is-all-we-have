# ruff: noqa: F811  (the client and holder fixtures come from test_api)
"""Screen copy the web page shows as it is: titles without the date, one short verb sentence per ledger
entry, the asked-for product apart from the options, user words for Spend Pass fields."""

import re

from conftest import CODE, TOKEN
from test_api import ask_milk, ask_mozzarella, auth, client, holder  # noqa: F401

MONEY = re.compile(r"\d euro\b|\b\d{4,}\b(?! €)")


def _milk_and_mozzarella(client, holder):
    milk = ask_milk(client, holder)
    client.post("/agent/v1/orders", headers=auth(holder), json={
        "requestId": milk["id"], "idempotencyKey": "milk-order-1",
        "choice": [{"productId": "464306", "salesQty": 1000, "priceCents": 101}]})
    client.post("/api/demo/stock-out", headers={"X-Demo-Token": TOKEN})
    return milk, ask_mozzarella(client, holder)


def test_title_text_has_no_date(client, holder):
    _milk_and_mozzarella(client, holder)
    r2 = client.get("/api/requests/R-2").json()
    assert r2["title"].endswith("by Mon 16 Nov")
    assert r2["titleText"] == "200 bags of lactose-free mozzarella 125 g"
    assert {i["id"]: i["titleText"] for i in client.get("/api/inbox").json()} == {
        "R-1": "1,000 litres of lactose-free milk", "R-2": "200 bags of lactose-free mozzarella 125 g"}
    heads = client.get("/api/ledger").json()["groups"]
    assert heads == [{"requestId": "R-1", "titleText": "1,000 litres of lactose-free milk"},
                     {"requestId": "R-2", "titleText": "200 bags of lactose-free mozzarella 125 g"}]


def test_ledger_display_text(client, holder):
    _milk_and_mozzarella(client, holder)
    oid = client.get("/api/requests/R-2").json()["orderId"]
    client.post(f"/api/orders/{oid}/approve", headers={"X-Approve-Code": CODE})
    entries = client.get("/api/ledger").json()["entries"]
    shown = [e["displayText"] for e in entries]
    assert shown[0] == "Asked for 1,000 litres of lactose-free milk by Mon 16 Nov, budget 1,200.00 €."
    assert entries[0]["sentence"].startswith("The agent asked for 1000 litres")  # the raw text stays
    placed = [e for e in entries if e["kind"] == "order"]
    assert [(e["actor"], e["actorText"]) for e in placed] == [("validio", "Validio")] * 2  # Validio places, the agent asks
    assert placed[0]["displayText"] == \
        "Placed O-1: 1,000 × 1 l of lactose-free semi-skimmed milk for 1,010.00 € without asking you."
    assert "Asked you: the substitute is not on Valio's list." in shown
    assert "Approved 10 × 2.5 kg of mozzarella-fontal crumbled cheese for 180.10 €." in shown
    for e in entries:
        t = e["displayText"]
        assert not t.startswith(e["actorText"] + " "), t
        assert len(re.findall(r"\bO-\d+\b", t)) <= 1, t
        assert not MONEY.search(t), t
        assert len(t.split()) <= 20, t


def test_asked_for_product_stands_apart(client, holder):
    _milk_and_mozzarella(client, holder)
    r2 = client.get("/api/requests/R-2").json()
    assert r2["askedFor"] == {"productId": "466375", "displayName": "Lactose-free mozzarella 125 g",
                              "stateText": "Out of stock at Valio (simulated, Valio really has 11,603 bags)"}
    listed = [o["productId"] for ln in r2["lines"]
              for o in ln["options"] + (ln.get("substitutes") or []) + (ln.get("beyondList") or [])]
    assert "466375" not in listed


def test_spend_pass_fields_in_user_words(client, holder):
    ask_milk(client, holder)
    sp = client.get("/api/spend-passes/M-1").json()
    words = sp["disclosedText"] + sp["hiddenText"]
    assert "preferred labels" in words and "orders alone up to" in words
    assert not {"prefer labels", "auto limit"} & set(words)


def test_footprint_note_is_short(client, holder):
    req = ask_milk(client, holder)
    note = client.get(f"/api/requests/{req['id']}").json()["lines"][0]["note"]
    assert len(note.split()) <= 14 and "1.1 kg CO2e per kg" in note
