# ruff: noqa: F811  (the client and holder fixtures come from test_api)
"""Screen copy the web page shows as it is: titles without the date, one short verb sentence per ledger
entry, the asked-for product apart from the options, user words for Spend Pass fields."""

import re

from asking import stockout
from conftest import CODE
from test_api import ask_milk, ask_mozzarella, auth, client, holder  # noqa: F401

MONEY = re.compile(r"\d euro\b|\b\d{4,}\b(?! €)")


def _milk_and_mozzarella(client, holder):
    milk = ask_milk(client, holder)
    client.post("/agent/v1/orders", headers=auth(holder), json={
        "requestId": milk["id"], "idempotencyKey": "milk-order-1",
        "choice": [{"productId": "464306", "salesQty": 1000, "priceCents": 101}]})
    stockout()
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
                     {"requestId": "demo", "titleText": "Demo"},
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
        "Ordered O-1: 1,000 × 1 l of lactose-free semi-skimmed milk for 1,010.00 € without asking you."
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
                              "stateText": "Simulated stock-out for this demo. Valio's live count is 11,603 bags."}
    listed = [o["productId"] for ln in r2["lines"]
              for o in ln["options"] + (ln.get("substitutes") or []) + (ln.get("beyondList") or [])]
    assert "466375" not in listed


def test_spend_pass_fields_in_user_words(client, holder):
    ask_milk(client, holder)
    sp = client.get("/api/spend-passes/M-1").json()
    words = sp["disclosedText"] + sp["hiddenText"]
    assert "preferred labels" in words and "auto-orders up to" in words
    assert not {"prefer labels", "auto limit"} & set(words)


def test_footprint_note_is_short(client, holder):
    req = ask_milk(client, holder)
    note = client.get(f"/api/requests/{req['id']}").json()["lines"][0]["note"]
    assert len(note.split()) <= 14 and "1.1 kg CO2e per kg" in note


def test_waiting_inbox_says_why_it_asks(client, holder):
    _milk_and_mozzarella(client, holder)
    item = {i["id"]: i for i in client.get("/api/inbox").json()}["R-2"]
    assert item["status"] == "waiting"
    assert item["summary"] == "Out of stock (simulated). The swap needs you."
    assert item["sentence"] == "Order 10 × 2.5 kg of mozzarella-fontal crumbled cheese for 180.10 €?"


def test_question_summary_keeps_its_question_mark():
    from validio.api import display as d
    assert d.summary("Order 10 × 2.5 kg of cheese for 180.10 €?") == "Order 10 × 2.5 kg of cheese for 180.10 €?"


def test_chosen_swap_says_what_it_is(client, holder):
    _milk_and_mozzarella(client, holder)
    line = client.get("/api/requests/R-2").json()["lines"][0]
    opts = [*line["options"], *(line.get("substitutes") or []), *(line.get("beyondList") or [])]
    chosen = [o for o in opts if o["verdict"] == "chosen"]
    assert [o["productId"] for o in chosen] == ["465256"]
    assert chosen[0]["shortText"] == "Cheapest lactose-free swap."
    r1 = client.get("/api/requests/R-1").json()["lines"][0]
    assert [o["shortText"] for o in r1["options"] if o["verdict"] == "chosen"] == [
        "Cheapest, always delivered in full."]


def test_spend_pass_says_what_the_agent_sees(client, holder):
    _milk_and_mozzarella(client, holder)
    p = client.get("/api/spend-passes/M-1").json()
    assert p["seesText"] == "The agent sees your limits and diet rules, not who approves or your preferred labels."


def test_stange_reads_naturally():
    from validio.text.format import short_name
    assert short_name("Topfoods mozzarella stange sliced lactose free 400g frozen") == \
        "Lactose-free sliced mozzarella stange 400 g"


def test_checked_facts_as_a_list(client, holder):
    ask_milk(client, holder)
    line = client.get("/api/requests/R-1").json()["lines"][0]
    milk = next(o for o in line["options"] if o["productId"] == "464306")
    assert milk["checks"] == ["Price 1.01 €", "Order cut-off 15 Nov 17:00", "Delivered in full in 100 % of orders",
                              "Free from lactose"]


def test_why_reasons_leave_out_the_short_text(client, holder):
    ask_milk(client, holder)
    line = client.get("/api/requests/R-1").json()["lines"][0]
    by_id = {o["productId"]: o for o in line["options"]}
    milk, dearer = by_id["464306"], by_id["464401"]
    assert milk["whyReasons"] == [r for r in milk["reasons"] if "Cheapest safe option" not in r]
    assert len(milk["whyReasons"]) == len(milk["reasons"]) - 1
    assert not any("more than the cheapest" in r for r in dearer["whyReasons"])
    assert len(dearer["whyReasons"]) == len(dearer["reasons"]) - 1
    down = [o for o in line["options"] if o.get("groupText")]
    for o in down:
        short = o["shortText"].rstrip(".")
        assert not any(r.rstrip(".") == short for r in o["whyReasons"])


def test_why_reasons_unit():
    from validio.api import display as d
    reasons = ["Not lactose free.", "Lists milk."]
    assert d.why_reasons(reasons, "Not lactose free.") == ["Lists milk."]
    assert d.why_reasons(["Order cut-off 12 Nov 15:00 has passed."], "Order cut-off 12 Nov 15:00 has passed.") == []
    assert d.why_reasons(["A.", "1,400.00 € is over the hard cap of 1,200.00 €."],
                         "1,400.00 € is over the 1,200.00 € hard cap.") == ["A."]


def test_density_round_request_texts(client, holder):
    _milk_and_mozzarella(client, holder)
    r1 = client.get("/api/requests/R-1").json()
    r2 = client.get("/api/requests/R-2").json()
    # D1: when Valio was read live, and the asked-for live count for the chosen row's fold
    assert r1["liveAt"] == "10:00" and r2["liveAt"] == "10:14"
    assert r2["liveCountText"] == "Valio's live count of lactose-free mozzarella 125 g: 11,603 bags."
    assert "liveCountText" not in r1
    # D2: the only place that names the stock-out, "simulated" once
    assert r2["leadText"] == "Out of stock (simulated). Swap not on Valio's list."
    assert "leadText" not in r1
    shown = [r2["leadText"], r2["liveCountText"], r2["askedFor"]["stateText"]]
    assert sum("simulated" in s.lower() for s in shown[:2]) == 1
    # D5: price side and chosen rows
    opts = {o["productId"]: o for o in r1["lines"][0]["options"]}
    assert opts["464401"]["shortText"] == "+90.00 €"
    assert opts["464306"]["shortText"] == "Cheapest, always delivered in full."
    line = r2["lines"][0]
    chosen = next(o for o in [*line["options"], *(line.get("beyondList") or [])] if o["verdict"] == "chosen")
    assert chosen["shortText"] == "Cheapest lactose-free swap."
    # D6: at most five facts in a fixed order, no CO2, labels, allergens or raw stock placeholder
    assert opts["464306"]["checks"] == ["Price 1.01 €", "Order cut-off 15 Nov 17:00",
                                        "Delivered in full in 100 % of orders", "Free from lactose"]
    assert chosen["checks"] == ["Price 18.01 €", "Order cut-off 15 Nov 17:00",
                                "Delivered in full in 100 % of orders", "Free from lactose"]
