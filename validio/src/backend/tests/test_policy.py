"""Step 6, Hard Lines: Cedar decides from typed whole numbers and yes/no values, a block always wins.

Numbers come from the blueprint and the build notes (scene 2, 462921, the parmesan split)."""

from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest
from jwcrypto.jwk import JWK

from validio.policy.decide import (
    POLICY_FILE,
    Outcome,
    PolicyContext,
    PolicyError,
    build_context,
    decide,
    load_policy,
)
from validio.policy.mandate import (
    AUDIENCE,
    DEMO_CLAIMS,
    DEMO_SD_FIELDS,
    NonceStore,
    issue_mandate,
    present,
    verify_presentation,
)

NOW = datetime.fromisoformat("2026-11-14T10:00:00+02:00")


@pytest.fixture(scope="module")
def mandate():
    kitchen, agent = JWK.generate(kty="EC", crv="P-256"), JWK.generate(kty="EC", crv="P-256")
    issuance = issue_mandate(DEMO_CLAIMS, DEMO_SD_FIELDS, kitchen, agent)
    nonces = NonceStore()
    token = present(issuance, {"autoLimitCents", "hardCapCents", "diet"}, agent, AUDIENCE, nonces.issue(NOW))
    return verify_presentation(
        token, kitchen_pub=kitchen, issuer="kitchen:hotel-espoo", aud=AUDIENCE, nonces=nonces, now=NOW
    )


def scene2(mandate, **kw):
    # 464306 Valio Arki Eila 1 l: 1000 ST at 1.01 EUR, lactose consistent, stock attested, Stock cut-off open
    args = {
        "total_cents": 1000 * 101,
        "diet_grades": {"FREE_FROM_LACTOSE": "consistent"},
        "quantity_grade": "attested",
        "cutoff_ok": True,
        "category": "10400",
    }
    args.update(kw)
    return build_context(mandate, **args)


def test_scene2_464306_allow(mandate):
    d = decide(scene2(mandate), product_id="464306")
    assert d.outcome is Outcome.ALLOW
    assert d.rule_ids == ["auto-order"]


def test_over_hard_cap_denied(mandate):
    # 462921 Eila organic: 200 KI of 5 l at 10.97 EUR = 2194.00 EUR, over the 2000 EUR hard cap
    d = decide(scene2(mandate, total_cents=200 * 1097, quantity_grade="unknown"), product_id="462921")
    assert d.context["totalCents"] == 219400
    assert d.outcome is Outcome.DENY
    assert "never-over-hard-cap" in d.rule_ids


def test_contradicted_claim_denied_under_budget(mandate):
    d = decide(scene2(mandate, diet_grades={"FREE_FROM_LACTOSE": "contradicted"}), product_id="465346")
    assert d.context["totalCents"] < d.context["autoLimitCents"]
    assert d.outcome is Outcome.DENY
    assert d.rule_ids == ["never-break-diet"]


def test_463038_escalates(mandate):
    # Terminal 999999 = unknown quantity, cut-off 12 Nov passed, 50 KI at 31.31 EUR
    d = decide(scene2(mandate, total_cents=50 * 3131, quantity_grade="unknown", cutoff_ok=False), "463038")
    assert d.outcome is Outcome.ESCALATE
    assert d.rule_ids == ["ask-human"]


def test_unchecked_claim_escalates(mandate):
    d = decide(scene2(mandate, diet_grades={"FREE_FROM_LACTOSE": "unchecked"}), product_id="466375")
    assert d.outcome is Outcome.ESCALATE


def test_missing_diet_grade_escalates(mandate):
    d = decide(scene2(mandate, diet_grades={}), product_id="463968")
    assert d.context["dietUnchecked"] is True
    assert d.outcome is Outcome.ESCALATE


def test_over_auto_limit_under_cap_escalates(mandate):
    d = decide(scene2(mandate, total_cents=120001), product_id="464306")
    assert d.outcome is Outcome.ESCALATE


def test_outside_list_substitute_escalates(mandate):
    # 463383 grated mozzarella, found outside Valio's list: 10 bags for 196.60 EUR
    ctx = scene2(mandate, total_cents=19660, is_substitute=True, on_valio_list=False, category="10600")
    assert decide(ctx, product_id="463383").outcome is Outcome.ESCALATE


def test_listed_substitute_split_within_limit_allows(mandate):
    # parmesan: 137 x 463968 plus 40 x 469648 for 772.49 EUR against 754.00 EUR usual, 2.5 % more
    ctx = scene2(
        mandate,
        total_cents=77249,
        split_base_cents=75400,
        is_substitute=True,
        on_valio_list=True,
        diet_grades={"FREE_FROM_LACTOSE": "consistent"},
        category="10600",
    )
    assert ctx.split_extra_bp == 246  # 18.49 / 754.00, rounded up to whole basis points
    d = decide(ctx, product_id="469648")
    assert d.outcome is Outcome.ALLOW


def test_split_over_limit_escalates(mandate):
    ctx = scene2(mandate, total_cents=79171, split_base_cents=75400, on_valio_list=True, category="10600")
    assert ctx.split_extra_bp == 501
    assert decide(ctx, product_id="469648").outcome is Outcome.ESCALATE


def test_drift_flag_escalates(mandate):
    ctx = scene2(mandate, drift_flag=True, is_renewal=True)
    assert decide(ctx, product_id="466375").outcome is Outcome.ESCALATE


def test_category_outside_pass_denied(mandate):
    assert decide(scene2(mandate, category="20100"), "x").outcome is Outcome.DENY


def test_undisclosed_budget_escalates(mandate):
    # no auto limit disclosed: never allow alone
    ctx = replace(scene2(mandate), auto_limit_cents=0)
    assert decide(ctx, product_id="464306").outcome is Outcome.ESCALATE
    no_limit = replace(mandate, auto_limit_cents=None)
    ctx = scene2(no_limit)
    assert ctx.auto_limit_cents == 0
    assert decide(ctx, product_id="464306").outcome is Outcome.ESCALATE


def test_undisclosed_hard_cap_denies(mandate):
    ctx = scene2(replace(mandate, hard_cap_cents=None))
    assert decide(ctx, product_id="464306").outcome is Outcome.DENY


def test_undisclosed_diet_never_allows(mandate):
    ctx = scene2(replace(mandate, diet=None))
    assert ctx.diet_unchecked is True
    assert decide(ctx, product_id="464306").outcome is not Outcome.ALLOW


def test_rule_ids_are_names(mandate):
    d = decide(
        scene2(mandate, total_cents=200 * 1097, diet_grades={"FREE_FROM_LACTOSE": "contradicted"}), "x"
    )
    assert sorted(d.rule_ids) == ["never-break-diet", "never-over-hard-cap"]
    assert all(not r.startswith("policy") for r in d.rule_ids)


def test_decision_has_a_sentence(mandate):
    assert "1010.00 EUR" in decide(scene2(mandate), "464306").sentence
    assert "hard cap" in decide(scene2(mandate, total_cents=219400), "462921").sentence


def test_context_is_whole_numbers_and_booleans(mandate):
    for v in scene2(mandate).to_cedar().values():
        assert type(v) in (int, bool)


def test_context_rejects_floats():
    with pytest.raises(TypeError):
        PolicyContext(
            total_cents=1010.0,
            auto_limit_cents=120000,
            hard_cap_cents=200000,
            diet_contradicted=False,
            diet_unchecked=False,
            quantity_attested=True,
            cutoff_ok=True,
        )


def test_policy_file_loads():
    policy = load_policy(POLICY_FILE)
    assert set(policy.rule_ids) == {"auto-order", "ask-human", "never-break-diet", "never-over-hard-cap"}


def test_policy_parse_error_raises(tmp_path):
    bad = tmp_path / "bad.cedar"
    # control: Cedar comments are //, a # comment is a parse error
    bad.write_text("# deny everything\n" + POLICY_FILE.read_text())
    with pytest.raises(PolicyError):
        load_policy(bad)


def test_policy_typo_in_context_raises(tmp_path):
    bad = tmp_path / "typo.cedar"
    bad.write_text(POLICY_FILE.read_text().replace("context.hardCapCents", "context.hardcapCents"))
    with pytest.raises(PolicyError):
        load_policy(bad)


def test_policy_without_id_raises(tmp_path):
    bad = tmp_path / "noid.cedar"
    bad.write_text(
        POLICY_FILE.read_text() + "\nforbid(principal, action, resource) when { context.salesBlock };\n"
    )
    with pytest.raises(PolicyError):
        load_policy(bad)


def test_broken_policy_stops_the_app(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from validio.api.app import app

    bad = tmp_path / "bad.cedar"
    bad.write_text(POLICY_FILE.read_text().replace("forbid(principal", "forbidd(principal", 1))
    monkeypatch.setenv("VALIDIO_POLICY_FILE", str(bad))
    with pytest.raises(PolicyError), TestClient(app):
        pass


def test_good_policy_starts_the_app(monkeypatch):
    from fastapi.testclient import TestClient

    from validio.api.app import app

    monkeypatch.delenv("VALIDIO_POLICY_FILE", raising=False)
    with TestClient(app) as c:
        assert c.get("/api/health").status_code == 200


def test_policy_file_lives_in_the_package():
    assert POLICY_FILE == Path(__file__).resolve().parents[1] / "validio" / "policy" / "policies.cedar"
