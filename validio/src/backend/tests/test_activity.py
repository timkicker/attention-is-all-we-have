"""Home and Activity (docs/ACCOUNTS-API.md, "Home and Activity"): one call for Home, one timeline of requests and
Steady Orders with a status filter and counts, and a detail that reads top to bottom (asked, checks, rule, result
or approval, proof). Each kitchen sees only its own."""

import pytest
from asking import EXAMPLE, ask, connect_demo_agent
from fastapi.testclient import TestClient
from test_accounts import SIGNUP, account_ctx, app_env  # noqa: F401

from validio.api import activity
from validio.api.settings import DEMO_RULES

CODE = "246810"
ITEM_KEYS = {"id", "kind", "status", "title", "why", "totalCents", "at", "orderId", "approvedByYou"}


def lower_alone(c, cents: int = 80000) -> None:
    r = c.put("/api/rules", json={**DEMO_RULES, "aloneUpToCents": cents, "code": CODE})
    assert r.status_code == 200, r.text


@pytest.fixture
def kitchen(app_env):  # noqa: F811
    """A demo copy with the demo agent: R-1 ordered alone, then the alone limit lowered, R-2 waits."""
    with TestClient(app_env) as c:
        c.post("/api/account/demo")
        k = account_ctx(c)
        connect_demo_agent(k)
        r1 = ask(k, EXAMPLE).request_id
        lower_alone(c)
        r2 = ask(k, EXAMPLE).request_id
        assert r1 and r2
        yield c, k, r1, r2


def test_activity_lists_requests_and_the_steady_order_newest_first(kitchen):
    c, _, r1, r2 = kitchen
    out = c.get("/api/activity").json()
    items = out["items"]
    assert all(set(it) == ITEM_KEYS for it in items), items[0]
    by_id = {it["id"]: it for it in items}
    assert by_id[r1]["status"] == "ordered" and by_id[r1]["orderId"] and by_id[r1]["kind"] == "request"
    assert by_id[r1]["why"] == "Under your 1,200.00 € limit, ordered alone"
    assert by_id[r1]["title"] == "1,000 litres of lactose-free milk" and by_id[r1]["totalCents"] == 101000
    assert by_id[r2]["status"] == "waiting" and by_id[r2]["why"] == "Over your 800.00 € limit for ordering alone"
    assert by_id["S-1"]["kind"] == "standing" and by_id["S-1"]["status"] == "standing"
    assert by_id["S-1"]["orderId"] is None and by_id["S-1"]["why"].startswith("Every Monday")
    ids = [it["id"] for it in items]
    assert ids.index(r2) < ids.index(r1) < ids.index("S-1")
    assert out["counts"] == {"all": 3, "ordered": 1, "waiting": 1, "blocked": 0, "standing": 1}


@pytest.mark.parametrize("status", ["ordered", "waiting", "blocked", "standing"])
def test_the_filter_keeps_the_counts(kitchen, status):
    c, *_ = kitchen
    everything = c.get("/api/activity").json()
    out = c.get("/api/activity", params={"status": status}).json()
    assert out["counts"] == everything["counts"]
    assert [it["id"] for it in out["items"]] == [it["id"] for it in everything["items"] if it["status"] == status]
    assert len(out["items"]) == out["counts"][status]


def test_an_unknown_filter_is_422(kitchen):
    c, *_ = kitchen
    assert c.get("/api/activity", params={"status": "placed"}).status_code == 422


def test_a_blocked_request_says_why_in_the_rules_words(kitchen):
    c, k, *_ = kitchen
    rid = ask(k, "9000 litres of lactose-free milk by Monday").request_id
    it = c.get(f"/api/activity/{rid}").json()["item"]
    assert it["status"] == "blocked" and it["why"] == "Above your 5,000.00 € limit, blocked", it
    assert c.get("/api/activity", params={"status": "blocked"}).json()["counts"]["blocked"] == 1


def test_detail_of_an_order_placed_alone(kitchen):
    c, _, r1, _ = kitchen
    d = c.get(f"/api/activity/{r1}").json()
    assert set(d) == {"item", "asked", "checks", "rule", "result", "approval", "proof"}
    assert d["asked"] == {"text": EXAMPLE, "agentName": "Demo agent"}
    labels = [x["label"] for x in d["checks"]]
    assert labels[:3] == ["Product", "Price", "Stock"] and "Allergens" in labels
    for x in d["checks"]:  # a note adds to its value, it never says it again
        assert not x["note"] or (not x["note"].lower().startswith(x["value"].lower()) and not x["note"].endswith("."))
    price = next(x for x in d["checks"] if x["label"] == "Price")
    assert price["value"].startswith("1.01 € per") and price["ok"] is True and price["note"].startswith("Valio price")
    allergens = next(x for x in d["checks"] if x["label"] == "Allergens")
    assert allergens["value"] == "Free from lactose" and allergens["ok"] is True
    assert d["rule"] == {"text": "Under your 1,200.00 € limit, ordered alone.", "version": 2}
    assert d["result"]["orderId"] == d["item"]["orderId"] and d["result"]["delivery"] == "2026-11-16"
    assert d["approval"] is None
    assert next(p["actor"] for p in d["proof"]) == "Demo agent"
    assert any(p["text"].startswith(f"Ordered {d['item']['orderId']}") for p in d["proof"])
    ledger = {e["hash"] for e in c.get("/api/ledger").json()["entries"]}
    assert all(len(p["hash"]) == 64 and p["hash"] in ledger for p in d["proof"])


def test_a_note_never_repeats_its_value():
    assert activity._note("Valio gives no real count", "Valio gives no real count, treated as in stock") == \
        "Treated as in stock"
    assert activity._note("Not on Valio's list", "Cheapest lactose-free swap.") == "Cheapest lactose-free swap"
    assert activity._note("In stock", "In stock") is None and activity._note("x", None) is None


def test_detail_while_waiting_then_approved(kitchen):
    c, _, _, r2 = kitchen
    d = c.get(f"/api/activity/{r2}").json()
    oid = d["item"]["orderId"]
    assert d["result"] is None and d["approval"]["orderId"] == oid
    assert d["approval"]["holdUntil"] == "2026-11-15T17:00:00+02:00"  # Valio's order cut-off
    assert d["rule"] == {"text": "Over your 800.00 € limit for ordering alone.", "version": 3}
    assert d["item"]["approvedByYou"] is False
    home = c.get("/api/home").json()
    assert [it["id"] for it in home["needsYou"]] == [r2]

    assert c.post(f"/api/orders/{oid}/approve", json={"code": CODE}).status_code == 200
    d = c.get(f"/api/activity/{r2}").json()
    assert d["item"]["status"] == "ordered" and d["item"]["why"] == "You approved it"
    assert d["item"]["approvedByYou"] is True
    assert next(i for i in c.get("/api/activity").json()["items"] if i["id"] == r2)["approvedByYou"] is True
    assert d["rule"]["text"] == "Over your 800.00 € limit for ordering alone. You approved it."
    assert d["approval"] is None and d["result"]["orderId"] == oid
    assert c.get("/api/home").json()["needsYou"] == []


def test_detail_of_a_rejected_order_is_blocked(kitchen):
    c, _, _, r2 = kitchen
    oid = c.get(f"/api/activity/{r2}").json()["item"]["orderId"]
    assert c.post(f"/api/orders/{oid}/reject", json={"code": CODE}).status_code == 200
    it = c.get(f"/api/activity/{r2}").json()["item"]
    assert (it["status"], it["why"]) == ("blocked", "You said no")


def test_detail_of_the_steady_order(kitchen):
    c, *_ = kitchen
    d = c.get("/api/activity/S-1").json()
    assert d["item"]["id"] == "S-1" and d["asked"]["agentName"] == "Validio"
    assert d["checks"] and all(x["label"] == "Product" for x in d["checks"])
    assert d["rule"]["text"].startswith("Under the Steady Order's own pass") and d["rule"]["version"] >= 1
    assert d["result"] is None and d["approval"] is None


def test_a_renewed_steady_order_shows_its_orders_and_what_still_waits(kitchen):
    c, *_ = kitchen
    assert c.post("/api/steady/S-1/renew", json={"code": CODE}).status_code == 200
    so = c.get("/api/steady/S-1").json()["lines"]
    placed = [ln for ln in so if ln["result"] in ("renewed", "split_renewed", "accepted")]
    waiting = sum(ln["result"] in ("waiting", "flagged") for ln in so)
    d = c.get("/api/activity/S-1").json()
    assert d["result"]["orderIds"] == list(dict.fromkeys(ln["orderId"] for ln in placed))
    assert d["result"]["orderId"] == d["result"]["orderIds"][0] and d["result"]["delivery"]
    assert d["item"]["totalCents"] == sum(ln["totalCents"] for ln in placed)  # a blocked line costs nothing
    assert (f"{waiting} waiting for you" in d["item"]["why"]) == bool(waiting)
    assert all(not x["note"] or not x["note"].endswith(".") for x in d["checks"])


@pytest.mark.parametrize("bad", ["R-99", "S-9", "O-1", "nothing"])
def test_unknown_ids_are_404(kitchen, bad):
    c, *_ = kitchen
    assert c.get(f"/api/activity/{bad}").status_code == 404


def test_home_in_one_call(kitchen):
    c, _, _r1, r2 = kitchen
    h = c.get("/api/home").json()
    assert set(h) == {"agent", "week", "setup", "needsYou", "latest"}
    assert h["agent"]["state"] == "active" and h["agent"]["name"] == "Demo agent" and h["agent"]["lastUsedAt"]
    assert h["week"] == {"usedCents": 101000, "capCents": DEMO_RULES["perWeekCents"]}
    assert h["setup"] == {"rulesSaved": True, "agentConnected": True, "firstOrder": True}
    assert [it["id"] for it in h["needsYou"]] == [r2]
    assert [it["id"] for it in h["latest"]] == [it["id"] for it in c.get("/api/activity").json()["items"]][:5]


def test_home_of_a_new_kitchen(app_env):  # noqa: F811
    with TestClient(app_env) as c:
        c.post("/api/account/signup", json=SIGNUP)
        h = c.get("/api/home").json()
        assert h["agent"] == {"state": "none", "name": None, "lastUsedAt": None}
        assert h["setup"] == {"rulesSaved": False, "agentConnected": False, "firstOrder": False}
        assert h["week"]["usedCents"] == 0 and h["needsYou"] == []
        assert [it["id"] for it in h["latest"]] == ["S-1"]
        c.post("/api/agent/pair")
        assert c.get("/api/home").json()["agent"]["state"] == "pairing"


def test_each_kitchen_sees_only_its_own(kitchen, app_env):  # noqa: F811
    c, _, r1, _r2 = kitchen
    with TestClient(app_env) as other:
        other.post("/api/account/signup", json=SIGNUP)
        assert other.get("/api/activity").json()["counts"] == {"all": 1, "ordered": 0, "waiting": 0, "blocked": 0,
                                                               "standing": 1}
        assert other.get(f"/api/activity/{r1}").status_code == 404
        assert other.get("/api/home").json()["needsYou"] == []
    assert c.get("/api/activity").json()["counts"]["all"] == 3


def test_closed_to_a_stranger(app_env):  # noqa: F811
    with TestClient(app_env, client=("203.0.113.9", 50000)) as stranger:
        for path in ("/api/home", "/api/activity", "/api/activity/R-1"):
            assert stranger.get(path).status_code in (401, 403), path
