"""Tests written to kill mutants that survived mutmut in policy/decide.py and trust/claims.py (docs/TESTING.md)."""

from dataclasses import replace
from datetime import date, datetime, timedelta

import pytest

from validio.policy.decide import (
    Outcome,
    PolicyContext,
    PolicyError,
    _ask,
    _escalation_reasons,
    build_context,
    context_for,
    decide,
    load_policy,
)
from validio.policy.mandate import DEMO_CLAIMS, _mandate
from validio.trust.claims import claim_check
from validio.trust.levels import TrustLevel
from validio.valio.models import Availability, ScheduleLine

from .test_mutants_matching import prod

NOW = datetime.fromisoformat("2026-11-14T10:00:00+02:00")
LF = "FREE_FROM_LACTOSE"
M1 = _mandate(dict(DEMO_CLAIMS))
OK = {LF: TrustLevel.CONSISTENT}


def ctx(**kw):
    args = {"total_cents": 100000, "diet_grades": OK, "quantity_grade": TrustLevel.ATTESTED, "cutoff_ok": True,
            "category": "104010", "quantity_covers": True, "delivery_in_time": True, "has_delivery_line": True}
    return build_context(kw.pop("mandate", M1), **{**args, **kw})


# build_context

def test_build_context_defaults_are_closed():
    c = ctx()
    assert (c.on_valio_list, c.is_renewal, c.is_substitute, c.is_split, c.sales_block, c.drift_flag) == \
        (False, False, False, False, False, False)
    assert c.split_extra_bp == 0


def test_build_context_passes_every_flag():
    # sales_block= and is_renewal= dropped from the call
    c = ctx(sales_block=True, is_renewal=True, on_valio_list=True, drift_flag=True)
    assert (c.sales_block, c.is_renewal, c.on_valio_list, c.drift_flag) == (True, True, True, True)


def test_undisclosed_diet_is_unchecked_not_contradicted():
    # contradicted, unchecked = True, True: an undisclosed diet would block instead of asking a person
    c = ctx(mandate=replace(M1, diet=None))
    assert (c.diet_contradicted, c.diet_unchecked) == (False, True)
    assert decide(c, "P-1").outcome is Outcome.ESCALATE


def test_undisclosed_caps_are_zero():
    c = ctx(mandate=replace(M1, auto_limit_cents=None, hard_cap_cents=None))
    assert (c.auto_limit_cents, c.hard_cap_cents) == (0, 0)


@pytest.mark.parametrize(("total", "base", "bp"), [(10500, 10000, 500), (9000, 10000, 0), (10001, 10000, 1),
                                                   (10000, 10000, 0)])
def test_split_extra_basis_points(total, base, bp):
    assert ctx(total_cents=total, split_base_cents=base).split_extra_bp == bp


@pytest.mark.parametrize("base", [0, -1])
def test_split_base_must_be_positive(base):
    with pytest.raises(ValueError, match="^split base must be positive$"):
        ctx(split_base_cents=base)


# context_for

def _avail(unit="ST", day=date(2026, 11, 16), closing=NOW + timedelta(hours=1), sales_block=False):
    return Availability("P-1", "Stock", closing, sales_block, [ScheduleLine(100.0, day, unit, False)], NOW)


def cfor(a, **kw):
    return context_for(M1, prod(category="104010"), a, total_cents=100000, now=NOW, sales_qty=3,
                       deliver_by=kw.pop("deliver_by", date(2026, 11, 16)), **kw)


def test_context_for_honest_line_allows():
    c = cfor(_avail())
    assert (c.quantity_attested, c.quantity_covers, c.delivery_in_time, c.cutoff_ok) == (True, True, True, True)
    assert (c.on_valio_list, c.is_renewal, c.sales_block) == (False, False, False)
    assert decide(c, "P-1").outcome is Outcome.ALLOW


def test_context_for_stock_in_an_unconvertible_unit_is_not_attested():
    # quantity_fact(availability, None) skips the unit check
    c = cfor(_avail(unit="KG"))
    assert c.quantity_attested is False


def test_context_for_request_deadline_counts():
    # effective_deadline(mandate, None) ignores the request's own earlier date
    c = cfor(_avail(day=date(2026, 11, 16)), deliver_by=date(2026, 11, 15))
    assert c.delivery_in_time is False


def test_context_for_cutoff_at_this_very_second_has_passed():
    # now < closing -> now <= closing
    assert cfor(_avail(closing=NOW)).cutoff_ok is False


def test_context_for_passes_sales_block_and_renewal():
    c = cfor(_avail(sales_block=True), is_renewal=True, on_valio_list=True)
    assert (c.sales_block, c.is_renewal, c.on_valio_list) == (True, True, True)


# _escalation_reasons: one sentence per failed fact, and none for a kept one

BASE = PolicyContext(total_cents=1000, auto_limit_cents=1000, hard_cap_cents=2000, diet_contradicted=False,
                     diet_unchecked=False, quantity_attested=True, cutoff_ok=True, quantity_covers=True,
                     delivery_in_time=True, substitutes_allowed=True, split_substitutes_allowed=True,
                     has_delivery_line=True, split_max_extra_bp=500)


def test_no_reason_when_everything_holds_even_at_the_limits():
    # total == auto limit is inside; split extra == max is inside
    assert _escalation_reasons(BASE) == []
    assert _escalation_reasons(replace(BASE, is_split=True, split_extra_bp=500)) == []
    assert _escalation_reasons(replace(BASE, is_substitute=True, on_valio_list=True)) == []
    assert _escalation_reasons(replace(BASE, is_split=True, is_substitute=True, on_valio_list=True)) == []
    assert _escalation_reasons(replace(BASE, on_valio_list=False, substitutes_allowed=False,
                                       split_substitutes_allowed=False)) == []


@pytest.mark.parametrize(("change", "sentence"), [
    ({"total_cents": 1001}, "10.01 € is over the auto limit of 10.00 €"),
    ({"diet_unchecked": True}, "a diet rule cannot be checked"),
    ({"quantity_attested": False}, "Valio does not confirm the stock"),
    ({"quantity_covers": False}, "Valio does not confirm enough stock"),
    ({"delivery_in_time": False}, "the delivery date is after the deadline or unknown"),
    ({"cutoff_ok": False}, "the order cut-off has passed"),
    ({"is_substitute": True, "on_valio_list": True, "substitutes_allowed": False},
     "the Spend Pass allows no substitutes"),
    ({"is_substitute": True, "on_valio_list": False}, "the substitute is not on Valio's list"),
    ({"is_split": True, "is_substitute": True, "on_valio_list": True, "split_substitutes_allowed": False},
     "the Spend Pass does not allow substitutes in a split"),
    ({"is_split": True, "split_extra_bp": 501}, "the split costs 5.01 % more, over the limit"),
    ({"drift_flag": True}, "Drift Watch flagged this line"),
])
def test_each_reason_alone(change, sentence):
    assert _escalation_reasons(replace(BASE, **change)) == [sentence]


def test_split_without_substitute_needs_no_substitute_permission():
    assert _escalation_reasons(replace(BASE, is_split=True, split_substitutes_allowed=False)) == []


# load_policy: errors say what broke, and the policy it returns decides

def test_load_policy_result_decides():
    # policy_set=None / schema=None in the returned Policy; default_policy() is cached, so call it directly
    p = load_policy()
    assert decide(BASE, "P-1", policy=p).outcome is Outcome.ALLOW
    assert decide(replace(BASE, total_cents=3000), "P-1", policy=p).outcome is Outcome.DENY


def _write(tmp_path, text):
    f = tmp_path / "p.cedar"
    f.write_text(text)
    return f



@pytest.mark.parametrize(("text", "message"), [
    (None, r"cannot read policy: "),
    ("permit(", r"p\.cedar: parse error: "),
    ("", r"p\.cedar: no policies$"),
    ("permit(principal, action, resource);", r"p\.cedar: policy0 has no @id$"),
    ('@id("a") permit(principal, action, resource);\n@id("a") forbid(principal, action, resource);',
     r"p\.cedar: @id 'a' used twice$"),
    ('@id("a") permit(principal == Nope::"x", action, resource);', r"p\.cedar: validation failed: "),
    ('@id("t") permit(principal == ?principal, action, resource);', r"p\.cedar: templates are not allowed$"),
])
def test_load_policy_errors(tmp_path, text, message):
    path = tmp_path / "missing.cedar" if text is None else _write(tmp_path, text)
    with pytest.raises(PolicyError, match=message):
        load_policy(path)


# trust/claims.py: grade and sentence for every claim kind

C, M, U, K = TrustLevel.CONTRADICTED, TrustLevel.MISSING, TrustLevel.UNCHECKED, TrustLevel.CONSISTENT


def item(claims=(), contains=(), key=None, lacs=0.0, allergen_data=True):
    return replace(prod(claims=claims, contains=contains, lacs=lacs), key_ingredients_en=key,
                   has_allergen_data=allergen_data)


@pytest.mark.parametrize(("p", "claim", "expected"), [
    (item(contains=("ML",)), LF, (C, ["lists lactose as contained"])),
    (item(), LF, (M, ["no lactose-free claim in Valio's data"])),
    (item(claims=(LF,), lacs=None), LF, (U, ["claims lactose free but gives no lactose value"])),
    (item(claims=("FREE_FROM_GLUTEN",), key="wheatflour, salt"), "FREE_FROM_GLUTEN",
     (C, ["key ingredients name wheatflour"])),
    (item(), "FREE_FROM_GLUTEN", (M, ["no gluten-free claim in Valio's data"])),
    (item(claims=("FREE_FROM_GLUTEN",), allergen_data=False), "FREE_FROM_GLUTEN",
     (U, ["claims gluten free but has no allergen data"])),
    (item(claims=("FREE_FROM_GLUTEN",)), "FREE_FROM_GLUTEN", (K, ["no gluten cereal listed"])),
    # vegan counts milk, egg and honey; vegetarian does not
    (item(claims=("VEGAN",), contains=("AM",)), "VEGAN", (C, ["lists milk as contained"])),
    (item(claims=("VEGETARIAN",), contains=("AM",)), "VEGETARIAN", (K, ["no animal ingredient listed"])),
    (item(claims=("VEGAN",), key="oats, honey"), "VEGAN", (C, ["key ingredients name honey"])),
    (item(claims=("VEGETARIAN",), key="oats, honey"), "VEGETARIAN", (K, ["no animal ingredient listed"])),
    (item(claims=("VEGETARIAN",), key="Beef stock"), "VEGETARIAN", (C, ["key ingredients name Beef"])),
    (item(), "VEGAN", (M, ["no vegan claim in Valio's data"])),
    (item(claims=("VEGAN",), allergen_data=False), "VEGAN", (U, ["claims vegan but has no allergen data"])),
    (item(claims=("ORGANIC",)), "ORGANIC", (U, ["nothing in the data to check it against"])),
    (item(), "ORGANIC", (M, ["no ORGANIC claim in Valio's data"])),
])
def test_claim_check_grade_and_sentence(p, claim, expected):
    assert claim_check(p, claim) == expected


# _ask: the request is checked against the schema, and any Cedar error is a PolicyError

@pytest.mark.parametrize("bad", [{"bogus": True}, {"cutoffOk": None}, {"totalCents": "1000"}])
def test_context_outside_the_schema_is_a_policy_error(bad):
    # schema=None / no schema: Cedar would evaluate a context the schema does not allow
    c = {k: v for k, v in {**BASE.to_cedar(), **bad}.items() if v is not None}
    with pytest.raises(PolicyError, match="^cedar error on PlaceOrder: .*failed to build request"):
        _ask(load_policy(), "PlaceOrder", "P-1", "buyer-1", c)
