"""Hard Lines under random input: whatever the amounts, stock, dates, claims and pass limits, the
invariants of the blueprint hold. Nothing over the hard cap is ever allowed, nothing above the auto limit
orders alone, a diet that is undisclosed or not backed by Valio's data never orders alone, a forbid wins."""

from dataclasses import fields, replace
from datetime import date, datetime, timedelta, timezone

import pytest
from hypothesis import assume, event, given, settings
from hypothesis import strategies as st

from validio.catalog.model import Product
from validio.policy.decide import DIET_KEPT, Outcome, PolicyContext, build_context, context_for, decide
from validio.policy.mandate import SUBSTITUTES_LISTED, Mandate, effective_deadline
from validio.trust.claims import claim_check
from validio.trust.levels import stock_in_sales_units
from validio.valio.models import Availability, ScheduleLine

TZ = timezone(timedelta(hours=2))
NOW = datetime(2026, 11, 14, 10, 0, tzinfo=TZ)
LACTOSE = "FREE_FROM_LACTOSE"
GRADES = ["consistent", "attested", "unchecked", "unknown", "missing", "contradicted", "untrusted", "bogus"]

money = st.integers(min_value=0, max_value=5_000_000)
maybe_money = st.none() | money


# The raw Cedar context: every field random

def _field_strategy(f):
    return money if f.type is int else st.booleans()


raw_context = st.builds(PolicyContext, **{f.name: _field_strategy(f) for f in fields(PolicyContext)})


@given(raw_context)
def test_raw_context_invariants(c):
    d = decide(c, "P-1")
    if c.total_cents > c.hard_cap_cents or c.diet_contradicted:
        assert d.outcome is Outcome.DENY, "a forbid must win over every permit"
    if d.outcome is Outcome.ALLOW:
        assert c.total_cents <= c.auto_limit_cents
        assert c.total_cents <= c.hard_cap_cents
        assert not c.diet_unchecked and not c.diet_contradicted
        assert c.quantity_attested and c.quantity_covers and c.delivery_in_time and c.cutoff_ok
        assert c.category_allowed and not c.sales_block and not c.drift_flag
        if c.is_substitute:
            assert c.on_valio_list and c.substitutes_allowed
        if c.is_split:
            assert c.split_extra_bp <= c.split_max_extra_bp
        if c.is_split and c.is_substitute:
            assert c.split_substitutes_allowed
    if d.outcome is Outcome.ESCALATE:
        assert c.total_cents <= c.hard_cap_cents and c.category_allowed and not c.sales_block


BAD_FLAGS = ["diet_unchecked", "diet_contradicted", "sales_block", "drift_flag"]
GOOD_FLAGS = ["quantity_attested", "quantity_covers", "delivery_in_time", "cutoff_ok", "category_allowed",
              "substitutes_allowed", "split_substitutes_allowed", "on_valio_list"]
RANK = {Outcome.ALLOW: 0, Outcome.ESCALATE: 1, Outcome.DENY: 2}


@given(raw_context, st.sampled_from(BAD_FLAGS + GOOD_FLAGS), st.integers(min_value=1, max_value=10**6))
def test_worse_facts_never_give_a_better_outcome(c, flag, more):
    """Monotone: a bad fact switched on, a good fact switched off or a higher total never helps."""
    base = RANK[decide(c, "P-1").outcome]
    worse = replace(c, **{flag: flag in BAD_FLAGS})
    assert RANK[decide(worse, "P-1").outcome] >= base
    pricier = replace(c, total_cents=c.total_cents + more)
    assert RANK[decide(pricier, "P-1").outcome] >= base


@given(raw_context)
def test_deny_wins_whatever_else_is_true(c):
    best = replace(c, **{f: False for f in BAD_FLAGS}, **{f: True for f in GOOD_FLAGS},
                   is_split=False, is_substitute=False, total_cents=min(c.total_cents, c.auto_limit_cents))
    assume(best.total_cents <= best.hard_cap_cents)
    assert decide(best, "P-1").outcome is Outcome.ALLOW
    for forbid in (replace(best, diet_contradicted=True), replace(best, total_cents=best.hard_cap_cents + 1)):
        d = decide(forbid, "P-1")
        assert d.outcome is Outcome.DENY
        assert {"never-break-diet", "never-over-hard-cap"} & set(d.rule_ids)


# The whole path from Valio's answer and the Spend Pass to the decision (context_for)

def product(lacs_g, claims, contains, sales_unit="ST", units=None, category="104010"):
    return Product(
        id="P-1", name_en="test milk", name_fi=None, category=category, vendor="Valio", sales_unit=sales_unit,
        base_unit="ST", units=units or {"ST": 1.0, "KI": 12.0}, base_volume_l=1.0, base_weight_kg=None,
        claims=frozenset(claims), contains=frozenset(contains), may_contain=frozenset(), free_from=frozenset(),
        has_allergen_data=True, lacs_g=lacs_g, key_ingredients_en=None, marketing_en=None, planted_en=None,
        substitutes=(), reliability=None, carbon_kg_per_kg=None, labels=frozenset(), temperature=None,
        deleted=False)


products = st.builds(
    product,
    lacs_g=st.sampled_from([None, 0.0, 0.01, 0.011, 0.5, 4.7]),
    claims=st.sets(st.sampled_from([LACTOSE, "LOW_LACTOSE", "FREE_FROM_GLUTEN"])),
    contains=st.sets(st.sampled_from(["ML", "AM", "UW"])),
    sales_unit=st.sampled_from(["ST", "KI"]),
    category=st.sampled_from(["104010", "106", "418900", "999", ""]),
)

days = st.dates(min_value=date(2026, 11, 1), max_value=date(2026, 12, 31))
amounts = st.sampled_from([0.0, 1.0, 36.0, 999.0, 1000.0, 999999.0, 9999999999.0]) | st.floats(0, 10**6)
schedule = st.builds(ScheduleLine, amount=amounts, available=days, sales_unit=st.sampled_from(["ST", "KI", "KG"]),
                     sales_block=st.booleans())
availabilities = st.none() | st.builds(
    Availability, product_id=st.just("P-1"), logistic_model=st.sampled_from(["Stock", "Terminal", None]),
    closing_time=st.none() | st.builds(lambda h: NOW + timedelta(hours=h), st.integers(-48, 96)),
    sales_block=st.booleans(), lines=st.lists(schedule, max_size=2), time_now=st.just(NOW))

mandates = st.builds(
    lambda auto, cap, diet, by, subs, extra, split_listed: Mandate(
        id="M-1", issuer="kitchen:hotel-espoo", holder="agent:buyer-1", not_before=0, expires=2**40,
        categories=("104", "106", "418"), deliver_by=by, substitutes=subs, split_max_extra_bp=extra,
        split_allow_listed=split_listed, auto_limit_cents=auto, hard_cap_cents=cap, diet=diet,
        prefer_labels=None, disclosed={}),
    auto=maybe_money, cap=maybe_money,
    diet=st.none() | st.just(()) | st.just((LACTOSE,)) | st.just((LACTOSE, "FREE_FROM_GLUTEN")),
    by=st.none() | st.sampled_from(["2026-11-16", "2026-11-14", "2026-12-24", "not a date", "16.11.2026"]),
    subs=st.none() | st.sampled_from([SUBSTITUTES_LISTED, "none", "LISTED_AND_RULES_KEPT", ""]),
    extra=st.integers(0, 1000), split_listed=st.booleans())


# totals start at 1 cent here; zero and below are test_free_or_negative_total_never_orders_alone
@given(mandates, products, availabilities, st.integers(1, 5_000_000), st.none() | st.integers(1, 100_000), st.none() | days,
       st.booleans(), st.booleans(), st.none() | st.integers(1, 5_000_000), st.booleans(),
       st.none() | st.lists(st.sampled_from([LACTOSE, "FREE_FROM_GLUTEN", "VEGAN"]), max_size=2))
def test_full_path_invariants(m, p, a, total, qty, by, is_sub, on_list, split_base, drift, line_claims):
    ctx = context_for(m, p, a, total_cents=total, now=NOW, is_substitute=is_sub, on_valio_list=on_list,
                      split_base_cents=split_base, drift_flag=drift, required_claims=line_claims,
                      sales_qty=qty, deliver_by=by)
    d = decide(ctx, p.id)
    event(f"outcome {d.outcome}")
    diet = tuple(line_claims) if line_claims is not None else m.diet
    grades = {c: str(claim_check(p, c)[0]) for c in diet or ()}

    if total > (m.hard_cap_cents or 0):
        assert d.outcome is Outcome.DENY, "over the hard cap (or no cap shown) is never allowed or asked"
    if "contradicted" in grades.values():
        assert d.outcome is Outcome.DENY
    if d.outcome is not Outcome.ALLOW:
        return
    # Only an ALLOW is left: every fact it rests on must really be there.
    assert m.auto_limit_cents is not None and total <= m.auto_limit_cents
    assert m.hard_cap_cents is not None and total <= m.hard_cap_cents
    assert diet is not None, "an undisclosed diet never orders alone"
    assert all(g in DIET_KEPT for g in grades.values()), grades
    assert a is not None and a.deliverable and a.closing_time is not None and NOW < a.closing_time
    stock = stock_in_sales_units(p, a)
    assert stock is not None and qty is not None and stock >= qty
    deadline = effective_deadline(m, by)
    assert deadline is not None and a.lines[0].available <= deadline
    if m.deliver_by is not None:
        assert a.lines[0].available <= date.fromisoformat(m.deliver_by), "a request never moves the signed date"
    assert any(p.category.startswith(c) for c in m.categories) and p.category != ""
    assert not drift
    if is_sub:
        assert on_list and m.substitutes == SUBSTITUTES_LISTED
    if split_base is not None:
        assert total * 10000 <= split_base * (10000 + m.split_max_extra_bp)
        if is_sub:
            assert m.split_allow_listed


# The same, near the edge: mostly good facts, so ALLOW really happens and each single bad fact gets tried.

def mostly(good, *bad):
    """`good` nine times in ten, else one of `bad`: ALLOW happens often and every single bad fact gets tried."""
    return st.sampled_from([good] * (9 * max(1, len(bad))) + list(bad))


near_products = st.builds(product, lacs_g=mostly(0.0, None, 0.02), claims=mostly({LACTOSE}, set()),
                          contains=mostly(set(), {"ML"}), sales_unit=mostly("ST", "KI"),
                          category=mostly("104010", "999"))
near_lines = st.lists(st.builds(ScheduleLine, amount=mostly(5000.0, 1000.0, 999.0, 36.0, 0.0, 999999.0),
                                available=mostly(date(2026, 11, 15), date(2026, 11, 16), date(2026, 11, 17)),
                                sales_unit=mostly("ST", "KI"), sales_block=mostly(False, True)),
                      min_size=1, max_size=2)
near_avail = st.builds(Availability, product_id=st.just("P-1"), logistic_model=mostly("Stock", "Terminal"),
                       closing_time=mostly(NOW + timedelta(hours=24), NOW - timedelta(minutes=1), NOW),
                       sales_block=mostly(False, True), lines=near_lines, time_now=st.just(NOW))
near_mandates = st.builds(
    lambda auto, cap, diet, by, subs: Mandate(
        id="M-1", issuer="kitchen:hotel-espoo", holder="agent:buyer-1", not_before=0, expires=2**40,
        categories=("104", "106", "418"), deliver_by=by, substitutes=subs, split_max_extra_bp=500,
        split_allow_listed=True, auto_limit_cents=auto, hard_cap_cents=cap, diet=diet, prefer_labels=None,
        disclosed={}),
    auto=mostly(120000, None, 50000), cap=mostly(200000, None, 100000), diet=mostly((LACTOSE,), None, ()),
    by=mostly("2026-11-16", None, "2026-11-15"), subs=mostly(SUBSTITUTES_LISTED, "none", None))


@settings(max_examples=400)
@given(near_mandates, near_products, near_avail, st.integers(1, 125_000) | st.integers(1, 260_000),
       st.integers(1, 1200), mostly(None, date(2026, 11, 13), date(2026, 11, 20)), mostly(False, True),
       st.booleans(), mostly(None, 100_000, 110_000), mostly(False, True), mostly(None, [LACTOSE], []))
def test_full_path_invariants_near_the_edge(m, p, a, total, qty, by, is_sub, on_list, split_base, drift, claims):
    test_full_path_invariants.hypothesis.inner_test(m, p, a, total, qty, by, is_sub, on_list, split_base, drift,
                                                    claims)


@given(st.sampled_from([None, (), (LACTOSE,)]), st.dictionaries(st.sampled_from([LACTOSE, "VEGAN"]),
                                                                  st.sampled_from(GRADES)))
def test_undisclosed_or_missing_claim_never_allows(diet, grades):
    m = Mandate(id="M-1", issuer="i", holder="h", not_before=0, expires=1, categories=("104",), deliver_by=None,
                substitutes=None, split_max_extra_bp=0, split_allow_listed=False, auto_limit_cents=100_000,
                hard_cap_cents=200_000, diet=diet, prefer_labels=None, disclosed={})
    c = build_context(m, total_cents=1000, diet_grades=grades, quantity_grade="attested", cutoff_ok=True,
                      category="104010", quantity_covers=True, delivery_in_time=True)
    d = decide(c, "P-1")
    if diet is None or (diet and grades.get(LACTOSE) not in DIET_KEPT):
        assert d.outcome is not Outcome.ALLOW
    if diet and grades.get(LACTOSE) == "contradicted":
        assert d.outcome is Outcome.DENY


@pytest.mark.parametrize("bad", [1.5, "1000", None, True])
def test_context_refuses_non_integer_money(bad):
    kw = {f.name: (0 if f.type is int else False) for f in fields(PolicyContext)}
    with pytest.raises(TypeError):
        PolicyContext(**{**kw, "total_cents": bad})


@pytest.mark.xfail(strict=True, reason="review-2 G1: a total of 0 or less cents orders alone, even with no limit shown")
@pytest.mark.parametrize("total", [0, -1, -101000])
def test_free_or_negative_total_never_orders_alone(total):
    """A price of zero or below is not a fact a person signed off on. With the auto limit undisclosed (0)
    it still passes `totalCents <= autoLimitCents`."""
    m = Mandate(id="M-1", issuer="i", holder="h", not_before=0, expires=1, categories=("104",), deliver_by=None,
                substitutes=None, split_max_extra_bp=0, split_allow_listed=False, auto_limit_cents=None,
                hard_cap_cents=None, diet=(), prefer_labels=None, disclosed={})
    c = build_context(m, total_cents=total, diet_grades={}, quantity_grade="attested", cutoff_ok=True,
                      category="104010", quantity_covers=True, delivery_in_time=True)
    assert decide(c, "P-1").outcome is not Outcome.ALLOW
