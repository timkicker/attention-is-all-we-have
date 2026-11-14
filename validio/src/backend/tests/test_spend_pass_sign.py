"""Play audit 5: the owner signs Spend Pass M-1 again with new limits. Same id, so the week's spend carries over;
an agent still holding the old copy is refused."""

from conftest import CODE
from test_api import auth, client, holder  # noqa: F401

from validio.agent.holder import Holder

NEW = {"autoLimitCents": 160000, "hardCapCents": 250000, "diet": ["FREE_FROM_LACTOSE"],
       "deliverBy": "2026-11-16", "substitutes": True}


def sign(client, body=None, code=CODE):  # noqa: F811
    return client.post("/api/spend-pass", json=body or NEW, headers={"X-Approve-Code": code} if code else {})


def ask(client, h, text, key):  # noqa: F811
    return client.post("/agent/v1/requests", headers=auth(h),
                       json={"lines": [{"text": text}], "deliverBy": "2026-11-16", "idempotencyKey": key})


def test_new_limits_decide_the_next_request(client, holder, ctx):  # noqa: F811
    before = ask(client, holder, "1500 litres of lactose-free milk by Monday", "a").json()
    assert before["decision"]["outcome"] == "ask_human"
    r = sign(client)
    assert r.status_code == 200, r.text
    view = r.json()
    assert (view["id"], view["autoLimitCents"], view["hardCapCents"]) == ("M-1", 160000, 250000)
    assert client.get("/api/spend-passes/M-1").json()["autoLimitCents"] == 160000
    fresh = Holder.from_seed(lambda: client.get("/agent/v1/nonce").json(), ctx.db_path, ctx.keys_dir)
    after = ask(client, fresh, "1500 litres of lactose-free milk by Monday", "b").json()
    assert after["decision"]["outcome"] == "auto_order", after["decision"]


def test_the_old_copy_is_refused(client, holder):  # noqa: F811
    assert sign(client).status_code == 200
    r = ask(client, holder, "500 litres of lactose-free milk by Monday", "old")
    assert r.status_code == 401 and "signed again" in r.json()["detail"]


def test_one_ledger_entry_by_the_owner(client):  # noqa: F811
    assert sign(client).status_code == 200
    entries = client.get("/api/ledger").json()["entries"]
    mine = [e for e in entries if e["actor"] == "owner"]
    assert len(mine) == 1
    assert mine[0]["sentence"] == ("Owner changed Spend Pass M-1. Orders alone up to 1,200.00 € → 1,600.00 €. "
                                   "Blocked above 2,000.00 € → 2,500.00 €.")
    led = client.get("/api/ledger").json()
    assert led["chain"]["ok"]


def test_the_limits_entry_is_whole_and_filed_under_the_pass(client, holder):  # noqa: F811
    ask(client, holder, "500 litres of lactose-free milk by Monday", "before")
    assert sign(client).status_code == 200
    led = client.get("/api/ledger").json()
    e = next(e for e in led["entries"] if e["kind"] == "spend_pass")
    assert e["displayText"] == "Orders alone up to 1,200.00 € → 1,600.00 €. Blocked above 2,000.00 € → 2,500.00 €."
    assert e["requestId"] == "M-1"
    assert {"requestId": "M-1", "titleText": "Rules"} in led["groups"]


def test_only_what_changed_is_named(client):  # noqa: F811
    assert sign(client, {**NEW, "autoLimitCents": 130000, "hardCapCents": 200000, "diet": [],
                         "substitutes": False}).status_code == 200
    e = next(e for e in client.get("/api/ledger").json()["entries"] if e["kind"] == "spend_pass")
    assert e["displayText"] == ("Orders alone up to 1,200.00 € → 1,300.00 €. Diet lactose free → none. "
                                "Substitutes from Valio's list → none alone.")
    assert sign(client, {**NEW, "autoLimitCents": 130000, "hardCapCents": 200000, "diet": [],
                         "substitutes": False}).status_code == 200
    last = [e for e in client.get("/api/ledger").json()["entries"] if e["kind"] == "spend_pass"][-1]
    assert last["displayText"] == "Signed again, nothing changed."


def test_the_weeks_spend_carries_over(client, holder, ctx):  # noqa: F811
    placed = ask(client, holder, "1000 litres of lactose-free milk by Monday", "w").json()
    assert placed["decision"]["outcome"] == "auto_order"
    o = client.post("/agent/v1/orders", headers=auth(holder), json={
        "requestId": placed["id"], "idempotencyKey": "w-o", "choice": [{"productId": "464306", "salesQty": 1000}]})
    assert o.json()["state"] == "placed", o.text
    used = client.get("/api/spend-passes/M-1").json()["usedCents"]
    assert used > 0
    assert sign(client).json()["usedCents"] == used


def test_alone_above_never_above_is_refused(client):  # noqa: F811
    r = sign(client, {**NEW, "autoLimitCents": 300000})
    assert r.status_code == 422 and "never above" in r.json()["detail"]


def test_needs_the_code(client):  # noqa: F811
    assert sign(client, code="000000").status_code == 403
    assert sign(client, code=None).status_code == 403
    assert client.get("/api/spend-passes/M-1").status_code in (200, 404)


def test_start_over_restores_the_seeded_pass(client, holder, ctx):  # noqa: F811
    assert sign(client).status_code == 200
    assert client.post("/api/demo/reset").status_code == 200
    fresh = Holder.from_seed(lambda: client.get("/agent/v1/nonce").json(), ctx.db_path, ctx.keys_dir)
    assert ask(client, fresh, "500 litres of lactose-free milk by Monday", "c").status_code == 200
    assert client.get("/api/spend-passes/M-1").json()["autoLimitCents"] == 120000


def test_a_diet_without_recordings_is_a_clean_refusal(client, ctx):  # noqa: F811
    assert sign(client, {**NEW, "diet": []}).status_code == 200
    fresh = Holder.from_seed(lambda: client.get("/agent/v1/nonce").json(), ctx.db_path, ctx.keys_dir)
    r = ask(client, fresh, "500 litres of milk by Monday", "plain")
    assert r.status_code in (200, 503), r.text
    if r.status_code == 503:
        assert "aren't recorded for this demo" in r.json()["detail"]
