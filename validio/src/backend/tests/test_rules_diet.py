"""The diet folded into the Rules (docs/ACCOUNTS-API.md, "Rules"): GET /api/rules carries it in words, PUT saves it
with the money and substitutes in one Save, one code, one new pass version. The "never" allergens are signed into
the pass and Cedar keeps them: a product that lists one is blocked, one that may contain one waits."""

from types import SimpleNamespace

import pytest
from asking import EXAMPLE, ask, connect_demo_agent
from fastapi.testclient import TestClient
from test_accounts import account_ctx, app_env  # noqa: F401

from validio.api.settings import DEMO_RULES
from validio.policy.decide import allergen_check
from validio.policy.mandate import NEVER_ALLERGENS, _mandate

CODE = "246810"


@pytest.fixture
def demo(app_env):  # noqa: F811
    with TestClient(app_env) as c:
        c.post("/api/account/demo")
        yield c


def versions(c) -> int:
    return c.get("/api/rules").json()["passVersion"]


def test_get_rules_has_the_diet_in_words(demo):
    d = demo.get("/api/rules").json()["diet"]
    assert d["mustBe"] == ["lactose-free"] and d["never"] == []
    assert d["options"]["mustBe"] == ["lactose-free", "gluten-free", "vegan"]
    assert {"nuts", "peanuts", "milk", "gluten", "eggs"} <= set(d["options"]["never"])


def test_one_save_one_code_one_version(demo):
    before, entries = versions(demo), len(demo.get("/api/ledger").json()["entries"])
    r = demo.put("/api/rules", json={**DEMO_RULES, "code": CODE,
                                     "diet": {"mustBe": ["lactose-free", "gluten-free"], "never": ["nuts"]}})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["passVersion"] == before + 1 and out["aloneUpToCents"] == DEMO_RULES["aloneUpToCents"]
    assert out["diet"]["mustBe"] == ["gluten-free", "lactose-free"] and out["diet"]["never"] == ["nuts"]
    new = demo.get("/api/ledger").json()["entries"][entries:]
    assert len(new) == 1 and new[0]["kind"] == "spend_pass"
    assert "Never contains nothing ruled out → nuts." in new[0]["sentence"], new[0]["sentence"]
    assert demo.get("/api/settings").json()["diet"] == ["FREE_FROM_GLUTEN", "FREE_FROM_LACTOSE"]


def test_a_save_without_diet_keeps_it(demo):
    demo.put("/api/rules", json={**DEMO_RULES, "code": CODE, "diet": {"mustBe": ["vegan"], "never": ["soy"]}})
    out = demo.put("/api/rules", json={**DEMO_RULES, "aloneUpToCents": 90000, "code": CODE}).json()
    assert out["diet"]["mustBe"] == ["vegan"] and out["diet"]["never"] == ["soy"]


def test_unknown_words_and_a_wrong_code_change_nothing(demo):
    before = versions(demo)
    bad = demo.put("/api/rules", json={**DEMO_RULES, "code": CODE, "diet": {"mustBe": ["keto"], "never": []}})
    assert bad.status_code == 422 and "keto" in bad.json()["detail"]
    bad = demo.put("/api/rules", json={**DEMO_RULES, "code": CODE, "diet": {"mustBe": [], "never": ["FREE_FROM_X"]}})
    assert bad.status_code == 422
    wrong = demo.put("/api/rules", json={**DEMO_RULES, "code": "000000", "diet": {"mustBe": [], "never": ["nuts"]}})
    assert wrong.status_code == 403
    assert versions(demo) == before and demo.get("/api/rules").json()["diet"]["never"] == []


def test_settings_diet_still_works_and_shows_in_the_rules(demo):
    r = demo.put("/api/settings/diet", json={"diet": ["VEGAN"], "code": CODE})
    assert r.status_code == 200 and r.json()["diet"] == ["VEGAN"]
    assert demo.get("/api/rules").json()["diet"]["mustBe"] == ["vegan"]


def test_never_milk_blocks_the_milk_and_never_nuts_lets_it_through(demo):
    k = account_ctx(demo)
    connect_demo_agent(k)
    demo.put("/api/rules", json={**DEMO_RULES, "code": CODE, "diet": {"mustBe": ["lactose-free"], "never": ["nuts"]}})
    ok = demo.get(f"/api/requests/{ask(k, EXAMPLE).request_id}").json()
    assert ok["status"] == "ordered_alone", ok["decision"]
    demo.put("/api/rules", json={**DEMO_RULES, "code": CODE, "diet": {"mustBe": ["lactose-free"], "never": ["milk"]}})
    rid = ask(k, EXAMPLE).request_id
    no = demo.get(f"/api/requests/{rid}").json()
    assert no["status"] == "blocked" and not no.get("orderId"), no["decision"]


def product(contains=(), may=(), data=True):
    return SimpleNamespace(contains=frozenset(contains), may_contain=frozenset(may), has_allergen_data=data)


def pass_with(never):
    return _mandate({"nbf": 0, "exp": 1, "neverContains": never})


@pytest.mark.parametrize(("never", "p", "want"), [
    ([], product(["AN"]), (False, False)),
    (["nuts"], product(["SH"]), (True, False)),  # hazelnuts are nuts
    (["nuts"], product(may=["SA"]), (False, True)),  # may contain almonds: a person looks
    (["nuts"], product(["AM"]), (False, False)),
    (["nuts"], product(data=False), (False, True)),  # no allergen data: never automatically
    (["peanuts"], product(["AN"]), (False, False)),
    (["unicorn"], product(), (False, True)),  # a word Validio does not know fails closed
])
def test_allergen_check(never, p, want):
    assert allergen_check(pass_with(never), p) == want


def test_every_never_word_has_codes_validio_can_name():
    from validio.text.format import ALLERGEN_WORDS

    assert all(codes and codes <= set(ALLERGEN_WORDS) for codes in NEVER_ALLERGENS.values())
