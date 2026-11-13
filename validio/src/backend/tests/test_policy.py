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
        "quantity_covers": True,
        "delivery_in_time": True,
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


# Wired to Fact Grades: the real catalog and the recorded answers of Valio's test API.


@pytest.fixture(scope="module")
def valio():
    from validio.config import load_settings
    from validio.valio.client import ValioClient

    s = load_settings()
    if not any(s.valio_cache.glob("price/*/*.json")):
        pytest.skip(f"needs_data: no recorded Valio answers in {s.valio_cache}, run make record")
    return ValioClient(s.valio_base_url, "", "replay", s.valio_cache)


def graded(catalog, valio, mandate, pid, quantity, **kw):
    from datetime import date

    from validio.policy.decide import context_for
    from validio.valio.budget import CallBudget

    monday = date(2026, 11, 16)
    q = valio.price([pid], monday, CallBudget(40))[pid]
    a = valio.availability([pid], monday, CallBudget(40))[pid]
    if "change" in kw:
        a = kw.pop("change")(a)
    kw.setdefault("sales_qty", quantity)
    kw.setdefault("deliver_by", monday)
    ctx = context_for(mandate, catalog.get(pid), a, total_cents=quantity * q.price_cents, now=NOW, **kw)
    return decide(ctx, product_id=pid)


def _line(a, **kw):
    return replace(a, lines=[replace(a.lines[0], **kw), *a.lines[1:]])


def test_graded_scene2_464306_allowed(catalog, valio, mandate):
    d = graded(catalog, valio, mandate, "464306", 1000)
    assert d.context["totalCents"] == 101000
    assert d.outcome is Outcome.ALLOW
    assert d.rule_ids == ["auto-order"]


def test_graded_462921_blocked_by_hard_cap(catalog, valio, mandate):
    d = graded(catalog, valio, mandate, "462921", 200)  # 200 KI of 5 l
    assert d.context["totalCents"] == 219400
    assert d.outcome is Outcome.DENY
    assert d.rule_ids == ["never-over-hard-cap"]


def test_graded_465346_contradicted_blocks_under_budget(catalog, valio, mandate):
    d = graded(catalog, valio, mandate, "465346", 1)
    assert d.context["totalCents"] == 1499
    assert d.context["dietContradicted"] is True
    assert d.outcome is Outcome.DENY
    assert "never-break-diet" in d.rule_ids


def test_graded_466375_unchecked_escalates(catalog, valio, mandate):
    d = graded(catalog, valio, mandate, "466375", 200)
    assert d.context["dietUnchecked"] is True
    assert d.outcome is Outcome.ESCALATE


def test_graded_463038_terminal_escalates(catalog, valio, mandate):
    d = graded(catalog, valio, mandate, "463038", 50)
    assert d.context["quantityAttested"] is False
    assert d.context["cutoffOk"] is False
    assert d.outcome is Outcome.ESCALATE


def test_graded_not_deliverable_never_allowed(catalog, valio, mandate):
    d = graded(catalog, valio, mandate, "473986", 1)
    assert d.context["quantityAttested"] is False
    assert d.outcome is not Outcome.ALLOW


def test_line_without_diet_ignores_the_pass_diet(catalog, valio, mandate):
    # parmesan claims nothing about lactose: as a line with no diet of its own it may order alone
    d = graded(catalog, valio, mandate, "469648", 10, required_claims=())
    assert d.context["dietUnchecked"] is False
    assert d.outcome is Outcome.ALLOW


def test_line_diet_replaces_the_pass_diet(catalog, valio, mandate):
    # 476523 lists wheat: a line that must stay gluten free is blocked even though the pass only says lactose free
    d = graded(catalog, valio, mandate, "476523", 1, required_claims=("FREE_FROM_GLUTEN",))
    assert d.context["dietContradicted"] is True
    assert d.outcome is Outcome.DENY


def test_default_line_diet_is_the_pass_diet(catalog, valio, mandate):
    d = graded(catalog, valio, mandate, "469648", 10)
    assert d.context["dietUnchecked"] is True
    assert d.outcome is Outcome.ESCALATE


# The final gate checks the amount and the date itself (review H1) and the limits the kitchen signed (H2).


def test_not_enough_stock_never_orders_alone(mandate):
    d = decide(scene2(mandate, quantity_covers=False), product_id="464306")
    assert d.outcome is Outcome.ESCALATE
    assert "Valio does not confirm enough stock" in d.sentence


def test_late_delivery_never_orders_alone(mandate):
    d = decide(scene2(mandate, delivery_in_time=False), product_id="464306")
    assert d.outcome is Outcome.ESCALATE
    assert "after the deadline" in d.sentence


def test_context_fails_closed_without_amount_and_date(mandate):
    args = {"total_cents": 101000, "diet_grades": {"FREE_FROM_LACTOSE": "consistent"},
            "quantity_grade": "attested", "cutoff_ok": True, "category": "10400"}
    ctx = build_context(mandate, **args)
    assert ctx.quantity_covers is False and ctx.delivery_in_time is False
    assert decide(ctx, product_id="464306").outcome is Outcome.ESCALATE


def test_pass_without_substitutes_escalates_listed_substitute(mandate):
    ctx = scene2(replace(mandate, substitutes="none"), is_substitute=True, on_valio_list=True)
    assert ctx.substitutes_allowed is False
    d = decide(ctx, product_id="469648")
    assert d.outcome is Outcome.ESCALATE
    assert "the Spend Pass allows no substitutes" in d.sentence


def test_unknown_substitutes_value_fails_closed(mandate):
    assert scene2(replace(mandate, substitutes="anything")).substitutes_allowed is False
    assert scene2(replace(mandate, substitutes=None)).substitutes_allowed is False
    assert scene2(mandate).substitutes_allowed is True


def test_split_with_listed_substitute_needs_the_pass_permission(mandate):
    no_split = replace(mandate, split_allow_listed=False)
    ctx = scene2(no_split, total_cents=77249, split_base_cents=75400, is_substitute=True, on_valio_list=True,
                 category="10600")
    assert ctx.split_substitutes_allowed is False
    d = decide(ctx, product_id="469648")
    assert d.outcome is Outcome.ESCALATE
    assert "the Spend Pass does not allow substitutes in a split" in d.sentence
    # control: the same split with the permission orders alone
    ok = scene2(mandate, total_cents=77249, split_base_cents=75400, is_substitute=True, on_valio_list=True,
                category="10600")
    assert decide(ok, product_id="469648").outcome is Outcome.ALLOW


def test_deadline_is_the_earlier_of_pass_and_request(mandate):
    from datetime import date

    from validio.policy.mandate import effective_deadline

    assert mandate.deliver_by == "2026-11-16"
    assert effective_deadline(mandate, date(2026, 12, 24)) == date(2026, 11, 16)
    assert effective_deadline(mandate, date(2026, 11, 15)) == date(2026, 11, 15)
    assert effective_deadline(mandate, None) == date(2026, 11, 16)
    assert effective_deadline(replace(mandate, deliver_by=None), None) is None
    assert effective_deadline(replace(mandate, deliver_by="soon"), date(2026, 11, 15)) == date.min


def test_graded_zero_stock_not_allowed(catalog, valio, mandate):
    d = graded(catalog, valio, mandate, "464306", 1000, change=lambda a: _line(a, amount=0.0))
    assert d.context["quantityCovers"] is False
    assert d.outcome is Outcome.ESCALATE


def test_graded_short_stock_not_allowed(catalog, valio, mandate):
    # 463380 has 698 ST in Stock: 699 is one too many
    assert graded(catalog, valio, mandate, "463380", 698, required_claims=()).context["quantityCovers"] is True
    d = graded(catalog, valio, mandate, "463380", 699, required_claims=())
    assert d.context["quantityCovers"] is False
    assert d.outcome is not Outcome.ALLOW


def test_graded_late_delivery_not_allowed(catalog, valio, mandate):
    from datetime import date

    late = lambda a: _line(a, available=date(2026, 11, 30))
    d = graded(catalog, valio, mandate, "464306", 1000, change=late)
    assert d.context["deliveryInTime"] is False
    assert d.outcome is Outcome.ESCALATE
    # a later date in the request does not move the signed deadline of 16 Nov
    d = graded(catalog, valio, mandate, "464306", 1000, change=late, deliver_by=date(2026, 12, 24))
    assert d.context["deliveryInTime"] is False
    assert d.outcome is Outcome.ESCALATE


def test_graded_without_amount_fails_closed(catalog, valio, mandate):
    d = graded(catalog, valio, mandate, "464306", 1000, sales_qty=None)
    assert d.context["quantityCovers"] is False
    assert d.outcome is Outcome.ESCALATE


def test_graded_unit_mismatch_counts_sales_units(catalog, valio, mandate):
    # 469054: 36 ST is 3 boxes of 12
    assert graded(catalog, valio, mandate, "469054", 3, required_claims=()).context["quantityCovers"] is True
    d = graded(catalog, valio, mandate, "469054", 4, required_claims=())
    assert d.context["quantityCovers"] is False
    assert d.outcome is not Outcome.ALLOW


def test_deny_without_forbid_names_a_rule(mandate):
    # category outside the pass: no forbid fires, the ledger still gets a rule id
    d = decide(scene2(mandate, category="20100"), "x")
    assert d.outcome is Outcome.DENY
    assert d.rule_ids == ["no-permit"]
