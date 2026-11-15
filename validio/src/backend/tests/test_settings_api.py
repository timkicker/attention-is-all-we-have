"""Rules, Diet and Kitchen settings (docs/ACCOUNTS-API.md). Rules and Diet sign Spend Pass M-1 again through
the same path as POST /api/spend-pass: one Save, one code, one new pass version, one ledger entry."""

import pytest
from conftest import CODE
from test_api import auth, client, holder  # noqa: F401

from validio.agent.holder import Holder

RULES = {"aloneUpToCents": 160000, "approvalUpToCents": 250000, "substitutes": "listed", "maxExtraPct": 0}


def put_rules(client, body=None, code=CODE):  # noqa: F811
    return client.put("/api/rules", json={**(body or RULES), **({"code": code} if code else {})})


def ask(client, h, text, key):  # noqa: F811
    return client.post("/agent/v1/requests", headers=auth(h),
                       json={"lines": [{"text": text}], "deliverBy": "2026-11-16", "idempotencyKey": key})


def fresh(client, ctx):  # noqa: F811
    return Holder.from_seed(lambda: client.get("/agent/v1/nonce").json(), ctx.db_path, ctx.keys_dir)


def test_rules_read_the_seeded_pass(client):  # noqa: F811
    r = client.get("/api/rules").json()
    assert r.pop("diet")["mustBe"] == ["lactose-free"]
    groups = r.pop("groups")
    assert (groups["all"], groups["codes"], len(groups["options"])) == (True, [], 43)
    assert {"code": "174", "name": "Fruit and vegetables"} in groups["options"]
    assert r == {"aloneUpToCents": 120000, "approvalUpToCents": 200000, "substitutes": "extra", "maxExtraPct": 5,
                 "perWeekCents": None, "saved": True, "passVersion": 1}


def test_rules_save_signs_a_new_version_that_decides(client, holder, ctx):  # noqa: F811
    assert ask(client, holder, "1500 litres of lactose-free milk by Monday", "a").json()["decision"]["outcome"] \
        == "ask_human"
    r = put_rules(client)
    assert r.status_code == 200, r.text
    assert {k: v for k, v in r.json().items() if k not in ("diet", "groups")} == {**RULES, "perWeekCents": None, "saved": True,
                                                                  "passVersion": 2}
    assert client.get("/api/rules").json()["passVersion"] == 2
    after = ask(client, fresh(client, ctx), "1500 litres of lactose-free milk by Monday", "b").json()
    assert after["decision"]["outcome"] == "auto_order", after["decision"]
    old = ask(client, holder, "500 litres of lactose-free milk by Monday", "old")
    assert old.status_code == 401 and "signed again" in old.json()["detail"]


def test_rules_save_writes_one_entry(client):  # noqa: F811
    assert put_rules(client).status_code == 200
    mine = [e for e in client.get("/api/ledger").json()["entries"] if e["kind"] == "spend_pass"]
    assert len(mine) == 1
    assert mine[0]["sentence"] == ("Owner changed Spend Pass M-1. Orders automatically up to 1,200.00 € → 1,600.00 €. "
                                   "Blocked above 2,000.00 € → 2,500.00 €. Extra for a split up to 5 % → none.")


def test_rules_keep_the_diet_and_diet_keeps_the_rules(client):  # noqa: F811
    assert client.put("/api/settings/diet", json={"diet": ["FREE_FROM_GLUTEN"], "code": CODE}).status_code == 200
    assert put_rules(client).status_code == 200
    assert client.get("/api/settings").json()["diet"] == ["FREE_FROM_GLUTEN"]
    assert client.put("/api/settings/diet", json={"diet": [], "code": CODE}).status_code == 200
    r = client.get("/api/rules").json()
    assert (r["aloneUpToCents"], r["approvalUpToCents"], r["passVersion"]) == (160000, 250000, 4)
    assert client.get("/api/spend-passes/M-1").json()["diet"] is not None


def test_substitutes_map_to_the_pass(client):  # noqa: F811
    for subs, pct in (("off", 0), ("listed", 0), ("extra", 12)):
        r = put_rules(client, {**RULES, "substitutes": subs, "maxExtraPct": pct})
        assert r.status_code == 200, r.text
        got = client.get("/api/rules").json()
        assert (got["substitutes"], got["maxExtraPct"]) == (subs, pct)
    view = client.get("/api/spend-passes/M-1").json()
    assert view["substitutes"] == "listed_and_rules_kept"
    assert view["split"] == {"maxExtraCostPct": 12.0, "allowListedSubstitutes": True}


def test_off_turns_swaps_and_split_swaps_off(client):  # noqa: F811
    assert put_rules(client, {**RULES, "substitutes": "off", "maxExtraPct": 7}).status_code == 200
    view = client.get("/api/spend-passes/M-1").json()
    assert view["substitutes"] == "never"
    assert view["split"] == {"maxExtraCostPct": 0.0, "allowListedSubstitutes": False}
    assert client.get("/api/rules").json()["maxExtraPct"] == 0


def test_rules_need_the_code(client):  # noqa: F811
    assert put_rules(client, code="000000").status_code == 403
    assert put_rules(client, code=None).status_code == 403
    assert client.put("/api/rules", json=RULES, headers={"X-Approve-Code": CODE}).status_code == 200
    assert client.get("/api/rules").json()["passVersion"] == 2


def test_rules_lock_after_five_wrong_codes(client):  # noqa: F811
    for _ in range(5):
        assert put_rules(client, code="000000").status_code == 403
    assert put_rules(client).status_code == 429


def test_rules_refuse_what_does_not_fit(client):  # noqa: F811
    assert put_rules(client, {**RULES, "aloneUpToCents": 300000}).status_code == 422
    assert put_rules(client, {**RULES, "aloneUpToCents": -1}).status_code == 422
    assert put_rules(client, {**RULES, "approvalUpToCents": 10_000_001}).status_code == 422
    assert put_rules(client, {**RULES, "substitutes": "any"}).status_code == 422
    assert put_rules(client, {**RULES, "substitutes": "extra", "maxExtraPct": 21}).status_code == 422
    assert client.get("/api/rules").json()["passVersion"] == 1


def test_zero_alone_means_everything_asks(client, ctx):  # noqa: F811
    assert put_rules(client, {**RULES, "aloneUpToCents": 0}).status_code == 200
    r = ask(client, fresh(client, ctx), "500 litres of lactose-free milk by Monday", "z").json()
    assert r["decision"]["outcome"] == "ask_human", r["decision"]


def test_settings_read(client):  # noqa: F811
    s = client.get("/api/settings").json()
    assert s["diet"] == ["FREE_FROM_LACTOSE"]
    assert set(s["kitchen"]) == {"name", "customerNumber", "deliveryAddress"}
    assert s["login"] == {"email": None}


def test_kitchen_save_needs_no_code_and_keeps_the_customer_number(client):  # noqa: F811
    before = client.get("/api/settings").json()["kitchen"]["customerNumber"]
    r = client.put("/api/settings/kitchen", json={"name": "  Hotel Espoo kitchen 2 ", "deliveryAddress": "Tie 1, Espoo",
                                                  "customerNumber": "999"})
    assert r.status_code == 200, r.text
    assert r.json()["kitchen"] == {"name": "Hotel Espoo kitchen 2", "customerNumber": before,
                                   "deliveryAddress": "Tie 1, Espoo"}
    assert client.get("/api/settings").json()["kitchen"]["name"] == "Hotel Espoo kitchen 2"
    assert client.get("/api/rules").json()["passVersion"] == 1  # nothing signed


def test_kitchen_needs_a_name(client):  # noqa: F811
    assert client.put("/api/settings/kitchen", json={"name": "  ", "deliveryAddress": ""}).status_code == 422
    assert client.put("/api/settings/kitchen", json={"name": "x" * 81, "deliveryAddress": ""}).status_code == 422


def test_diet_save_signs_once_and_writes_one_entry(client):  # noqa: F811
    r = client.put("/api/settings/diet", json={"diet": ["VEGAN", "FREE_FROM_LACTOSE", "VEGAN"], "code": CODE})
    assert r.status_code == 200, r.text
    assert r.json()["diet"] == ["FREE_FROM_LACTOSE", "VEGAN"]
    assert client.get("/api/rules").json()["passVersion"] == 2
    mine = [e for e in client.get("/api/ledger").json()["entries"] if e["kind"] == "spend_pass"]
    assert [e["sentence"] for e in mine] == ["Owner changed Spend Pass M-1. Diet lactose free → lactose free and vegan."]


def test_diet_needs_the_code(client):  # noqa: F811
    assert client.put("/api/settings/diet", json={"diet": [], "code": "111111"}).status_code == 403
    assert client.put("/api/settings/diet", json={"diet": ["HALAL"], "code": CODE}).status_code == 422
    assert client.get("/api/settings").json()["diet"] == ["FREE_FROM_LACTOSE"]


def test_the_old_spend_pass_route_keeps_the_rules_it_does_not_name(client):  # noqa: F811
    assert put_rules(client, {**RULES, "substitutes": "extra", "maxExtraPct": 9}).status_code == 200
    r = client.post("/api/spend-pass", headers={"X-Approve-Code": CODE}, json={
        "autoLimitCents": 100000, "hardCapCents": 200000, "diet": [], "deliverBy": "2026-11-16", "substitutes": True})
    assert r.status_code == 200, r.text
    assert client.get("/api/rules").json()["maxExtraPct"] == 9


def test_own_approval_code_replaces_the_server_code(client):  # noqa: F811
    from validio.api import codes

    assert client.put("/api/settings/approval-code", json={"current": "000000", "next": "135790"}).status_code == 403
    assert client.put("/api/settings/approval-code", json={"current": CODE, "next": "12345"}).status_code == 422
    assert client.put("/api/settings/approval-code", json={"current": CODE, "next": "135790"}).status_code == 204
    assert put_rules(client).status_code == 403  # the server's code no longer counts here
    assert put_rules(client, code="135790").status_code == 200
    assert codes.matches(codes.hash_code("135790"), "135790") and not codes.matches(codes.hash_code("135790"), "135791")


def test_the_code_is_stored_hashed(client, ctx):  # noqa: F811
    assert client.put("/api/settings/approval-code", json={"current": CODE, "next": "135790"}).status_code == 204
    import sqlite3

    con = sqlite3.connect(ctx.db_path)
    values = [v for (v,) in con.execute("select value from demo_state")]
    con.close()
    assert not any("135790" in v for v in values)
    assert any(v.startswith("scrypt$") for v in values)


# per account: Rules, Diet and the code work on the logged-in kitchen's own store

SIGNUP = {"name": "Kitchen A", "email": "a@example.org", "password": "correct horse",
          "customerNumber": "123456", "approvalCode": "135790"}


def _accounts(ctx, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from validio.api import accounts as acc_mod
    from validio.api.app import app

    monkeypatch.setenv("VALIDIO_ACCOUNTS", str(tmp_path / "accounts"))
    monkeypatch.setenv("VALIDIO_TEMPLATE", str(tmp_path / "template"))
    acc_mod._tries.clear()
    return TestClient(app, client=("203.0.113.9", 50000))  # not on this machine: only the session opens /api


def test_rules_and_diet_sign_the_accounts_own_pass(ctx, tmp_path, monkeypatch):
    with _accounts(ctx, tmp_path, monkeypatch) as c:
        assert c.post("/api/account/signup", json=SIGNUP).status_code == 201
        assert c.get("/api/rules").json()["saved"] is False
        assert put_rules(c).status_code == 403  # the server's code is not this kitchen's
        r = put_rules(c, code="135790")
        assert r.status_code == 200, r.text
        # version 2 is the signing for the account's own key (seed.rekey on create), the Rules sign version 3
        assert r.json()["saved"] is True and r.json()["passVersion"] == 3
        assert c.get("/api/account").json()["setup"]["rules"] is True
        d = c.put("/api/settings/diet", json={"diet": ["VEGAN"], "code": "135790"})
        assert d.status_code == 200 and d.json()["diet"] == ["VEGAN"]
        s = c.get("/api/settings").json()
        assert s["kitchen"]["customerNumber"] == "123456" and s["login"]["email"] == "a@example.org"
    assert client_rules_local(ctx)["passVersion"] == 1  # the local kitchen did not move


def client_rules_local(ctx):
    from fastapi.testclient import TestClient

    from validio.api.app import app

    with TestClient(app) as c:
        return c.get("/api/rules").json()


def test_kitchen_save_shows_on_the_account(ctx, tmp_path, monkeypatch):
    with _accounts(ctx, tmp_path, monkeypatch) as c:
        c.post("/api/account/signup", json=SIGNUP)
        r = c.put("/api/settings/kitchen", json={"name": "Kitchen B", "deliveryAddress": "Tie 1, Espoo"})
        assert r.status_code == 200
        a = c.get("/api/account").json()
        assert (a["name"], a["deliveryAddress"], a["setup"]["kitchen"]) == ("Kitchen B", "Tie 1, Espoo", True)


def test_changing_the_code_works_for_approvals_too(ctx, tmp_path, monkeypatch):
    with _accounts(ctx, tmp_path, monkeypatch) as c:
        c.post("/api/account/signup", json=SIGNUP)
        assert c.put("/api/settings/approval-code", json={"current": "135790", "next": "975310"}).status_code == 204
        assert put_rules(c, code="135790").status_code == 403
        assert put_rules(c, code="975310").status_code == 200
        # an own account has no borrowed Steady Order S-1 to renew (test_an_own_account_has_no_borrowed_steady_order)
        assert c.post("/api/steady/S-1/renew", json={"code": "975310"}).status_code == 404


def test_demo_copy_answers_to_246810_and_keeps_it(ctx, tmp_path, monkeypatch):
    with _accounts(ctx, tmp_path, monkeypatch) as c:
        a = c.post("/api/account/demo").json()
        assert a["demoCode"] == "246810"
        assert put_rules(c, code="246810").status_code == 200
        r = c.put("/api/settings/approval-code", json={"current": "246810", "next": "975310"})
        assert r.status_code == 403
        assert put_rules(c, code="246810").status_code == 200


def test_246810_is_not_a_signed_up_kitchens_code(ctx, tmp_path, monkeypatch):
    with _accounts(ctx, tmp_path, monkeypatch) as c:
        c.post("/api/account/signup", json=SIGNUP)
        assert put_rules(c, code="246810").status_code == 403


# per week: with a weekly limit on the pass, automatic orders and approval count per order and the week counts all orders

WEEKLY = {**RULES, "aloneUpToCents": 120000, "approvalUpToCents": 500000, "perWeekCents": 800000}


def _place_milk(client, ctx, key):  # noqa: F811
    h = fresh(client, ctx)
    req = ask(client, h, "1000 litres of lactose-free milk by Monday", key).json()
    o = client.post("/agent/v1/orders", headers=auth(h), json={
        "requestId": req["id"], "idempotencyKey": key + "-o", "choice": [{"productId": "464306", "salesQty": 1000}]})
    return req, o.json()


def test_rules_carry_a_weekly_limit(client):  # noqa: F811
    assert client.get("/api/rules").json()["perWeekCents"] is None  # the seeded pass has none
    r = put_rules(client, WEEKLY)
    assert r.status_code == 200, r.text
    assert r.json()["perWeekCents"] == 800000
    e = [e for e in client.get("/api/ledger").json()["entries"] if e["kind"] == "spend_pass"][-1]
    assert "Per week none → 8,000.00 €." in e["sentence"]
    assert put_rules(client, {**WEEKLY, "perWeekCents": 400000}).status_code == 422  # below the approval limit


def test_with_a_weekly_limit_each_order_is_judged_alone(client, ctx):  # noqa: F811
    assert put_rules(client, WEEKLY).status_code == 200
    first, o1 = _place_milk(client, ctx, "w1")
    assert first["decision"]["outcome"] == "auto_order" and o1["state"] == "placed", o1
    second, o2 = _place_milk(client, ctx, "w2")  # 2,020.00 € placed this week, still alone per order
    assert second["decision"]["outcome"] == "auto_order", second["decision"]
    assert o2["state"] == "placed", o2


def test_the_week_blocks_what_would_go_over(client, ctx):  # noqa: F811
    assert put_rules(client, {**WEEKLY, "perWeekCents": 500000}).status_code == 200
    for k in ("a", "b", "c", "d"):
        assert _place_milk(client, ctx, k)[1]["state"] == "placed"
    req = ask(client, fresh(client, ctx), "1000 litres of lactose-free milk by Monday", "e").json()
    assert req["decision"]["outcome"] == "block", req["decision"]
    assert "over the weekly limit of 5,000.00 €" in req["decision"]["sentence"]


def test_without_a_weekly_limit_each_order_is_judged_alone_too(client, ctx):  # noqa: F811
    _first, o1 = _place_milk(client, ctx, "x1")
    assert o1["state"] == "placed"
    second = ask(client, fresh(client, ctx), "1000 litres of lactose-free milk by Monday", "x2").json()
    assert second["decision"]["outcome"] == "auto_order", second["decision"]  # the Rules' limits are per order


def test_product_groups_narrow_and_widen_with_one_signed_version(client, holder, ctx):  # noqa: F811
    r = put_rules(client, {**RULES, "groups": {"all": False, "codes": ["106", "104", "104"]}})
    assert r.status_code == 200, r.text
    assert (r.json()["groups"]["all"], r.json()["groups"]["codes"]) == (False, ["104", "106"])
    from validio.api.settings import current_claims

    assert current_claims(ctx.db_path)["categories"] == ["104", "106"]  # signed into the pass
    entry = [e for e in client.get("/api/ledger").json()["entries"] if e["kind"] == "spend_pass"][-1]
    assert "Product groups all groups → Milk and dairy drinks; Cheese." in entry["sentence"]
    # a Save without groups keeps them
    assert put_rules(client).json()["groups"]["codes"] == ["104", "106"]
    r = put_rules(client, {**RULES, "groups": {"all": True, "codes": []}})
    assert (r.json()["groups"]["all"], current_claims(ctx.db_path)["categories"]) == (True, ["*"])


@pytest.mark.parametrize("groups,said", [
    ({"all": False, "codes": ["999"]}, "unknown product group '999'"),
    ({"all": False, "codes": ["17413"]}, "unknown product group '17413'"),
    ({"all": False, "codes": []}, "choose at least one product group, or all groups"),
])
def test_product_groups_refuse_what_valio_has_no_group_for(client, groups, said):  # noqa: F811
    before = client.get("/api/rules").json()["passVersion"]
    r = put_rules(client, {**RULES, "groups": groups})
    assert r.status_code == 422 and said in r.json()["detail"], r.text
    assert client.get("/api/rules").json()["passVersion"] == before


def test_a_product_outside_the_groups_names_its_group(client, holder, ctx):  # noqa: F811
    assert put_rules(client, {**RULES, "groups": {"all": False, "codes": ["106"]}}).status_code == 200
    req = ask(client, fresh(client, ctx), "500 litres of lactose-free milk by Monday", "milk").json()
    assert req.get("status") == "blocked", req
    assert req["decision"]["reasonCode"] == "outside_groups", req["decision"]
    assert req["decision"]["ownerText"] == "Not ordered: Milk and dairy drinks isn't in your product groups."
    detail = client.get(f"/api/activity/{req['id']}").json()
    assert detail["rule"]["text"] == "Milk and dairy drinks isn't in your product groups."
