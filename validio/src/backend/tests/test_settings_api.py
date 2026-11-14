"""Rules, Diet and Kitchen settings (docs/ACCOUNTS-API.md). Rules and Diet sign Spend Pass M-1 again through
the same path as POST /api/spend-pass: one Save, one code, one new pass version, one ledger entry."""

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
    assert r == {"aloneUpToCents": 120000, "approvalUpToCents": 200000, "substitutes": "extra", "maxExtraPct": 5,
                 "saved": True, "passVersion": 1}


def test_rules_save_signs_a_new_version_that_decides(client, holder, ctx):  # noqa: F811
    assert ask(client, holder, "1500 litres of lactose-free milk by Monday", "a").json()["decision"]["outcome"] \
        == "ask_human"
    r = put_rules(client)
    assert r.status_code == 200, r.text
    assert r.json() == {**{k: v for k, v in RULES.items()}, "saved": True, "passVersion": 2}
    assert client.get("/api/rules").json()["passVersion"] == 2
    after = ask(client, fresh(client, ctx), "1500 litres of lactose-free milk by Monday", "b").json()
    assert after["decision"]["outcome"] == "auto_order", after["decision"]
    old = ask(client, holder, "500 litres of lactose-free milk by Monday", "old")
    assert old.status_code == 401 and "signed again" in old.json()["detail"]


def test_rules_save_writes_one_entry(client):  # noqa: F811
    assert put_rules(client).status_code == 200
    mine = [e for e in client.get("/api/ledger").json()["entries"] if e["kind"] == "spend_pass"]
    assert len(mine) == 1
    assert mine[0]["sentence"] == ("Owner changed Spend Pass M-1. Alone up to 1,200.00 € → 1,600.00 €. "
                                   "Never above 2,000.00 € → 2,500.00 €. Extra for a split up to 5 % → none.")


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
