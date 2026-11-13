"""The decision path on the SYNTHETIC data set (tests/synthetic_data.py): runs in CI, where Valio's data is absent.

Need matching and Best Pick, Fact Grades, Hard Lines, Split Fill, the order service with approve and the ledger.
Every product and number here is invented."""

from dataclasses import replace
from datetime import date, datetime

import pytest
from synthetic_data import build

from validio.audit.log import AuditLog
from validio.catalog.store import Catalog
from validio.matching.need import parse_need, screen
from validio.matching.rank import rank
from validio.matching.split import decide_split, plan_split
from validio.orders.service import ApproveRefused, LineIn, OrderService
from validio.orders.store import Store
from validio.policy.decide import Outcome, context_for, decide
from validio.policy.mandate import Mandate
from validio.trust.levels import TrustLevel, quantity_fact
from validio.valio.budget import CallBudget
from validio.valio.client import ValioClient

NOW = datetime.fromisoformat("2026-11-14T10:00:00+02:00")
MON = date(2026, 11, 16)
PASS = Mandate(
    id="M-SYN", issuer="kitchen:synthetic", holder="agent:synthetic", not_before=0, expires=2**40,
    categories=("104", "106"), deliver_by="2026-11-16", substitutes="listed_and_rules_kept",
    split_max_extra_bp=500, split_allow_listed=True, auto_limit_cents=120000, hard_cap_cents=200000,
    diet=("FREE_FROM_LACTOSE",), prefer_labels=(), disclosed={"autoLimitCents": 120000},
)


@pytest.fixture(scope="module")
def syn(tmp_path_factory):
    db, cache = build(tmp_path_factory.mktemp("synthetic"))
    return Catalog(db), ValioClient("https://junction26.valioaimo.fi", "", "replay", cache)


@pytest.fixture(autouse=True)
def _placeholder_default(monkeypatch):
    monkeypatch.delenv("STRICT_PLACEHOLDER_STOCK", raising=False)


def live(syn, *ids):
    _, valio = syn
    b = CallBudget(40)
    return valio.price(list(ids), MON, b), valio.availability(list(ids), MON, b)


def judge(syn, pid, qty, mandate=PASS, change=None, **kw):
    cat, _ = syn
    q, a = live(syn, pid)
    av = change(a[pid]) if change else a[pid]
    ctx = context_for(mandate, cat.get(pid), av, total_cents=qty * q[pid].price_cents, now=NOW, sales_qty=qty,
                      deliver_by=MON, **kw)
    return decide(ctx, product_id=pid)


def test_every_product_is_marked_synthetic(syn):
    cat, _ = syn
    names = [cat.get(f"90000{i}").name_en for i in range(1, 10)]
    assert all(n.startswith("SYNTHETIC ") for n in names)


def test_best_pick_on_synthetic_milk(syn):
    cat, _ = syn
    need = parse_need("100 litres of lactose-free milk by Monday", NOW.date())
    cands, _ = screen(need, cat)
    q, a = live(syn, *[p.id for p in cands])
    ranked = {r.product.id: r for r in rank(need, cands, q, a, NOW)}
    order = [r.product.id for r in rank(need, cands, q, a, NOW)]
    assert order[0] == "900001" and ranked["900001"].accepted and ranked["900001"].total_cents == 10000
    assert any("Not lactose free" in x for x in ranked["900003"].reasons)
    assert any("Only 3 KI in stock, 9 needed" in x for x in ranked["900004"].reasons)
    assert any("no delivery date" in x for x in ranked["900008"].reasons)


def test_allowed_inside_every_limit(syn):
    d = judge(syn, "900001", 100)
    assert d.outcome is Outcome.ALLOW and d.rule_ids == ["auto-order"]


def test_short_stock_asks(syn):
    low = lambda a: replace(a, lines=[replace(a.lines[0], amount=99.0)])
    d = judge(syn, "900001", 100, change=low)
    assert d.context["quantityCovers"] is False and d.outcome is Outcome.ESCALATE


def test_late_delivery_asks(syn):
    late = lambda a: replace(a, lines=[replace(a.lines[0], available=date(2026, 11, 30))])
    d = judge(syn, "900001", 100, change=late)
    assert d.context["deliveryInTime"] is False and d.outcome is Outcome.ESCALATE


def test_unit_mismatch_counts_boxes(syn):
    assert judge(syn, "900004", 3).context["quantityCovers"] is True
    assert judge(syn, "900004", 4).context["quantityCovers"] is False


def test_contradicted_diet_blocks(syn):
    d = judge(syn, "900003", 10)
    assert d.outcome is Outcome.DENY and d.rule_ids == ["never-break-diet"]


def test_hard_cap_blocks(syn):
    d = judge(syn, "900002", 1000)  # 2500.00 EUR
    assert d.outcome is Outcome.DENY and "never-over-hard-cap" in d.rule_ids


def test_no_delivery_line_blocks(syn):
    d = judge(syn, "900008", 1)
    assert d.context["hasDeliveryLine"] is False and d.outcome is Outcome.DENY


def test_terminal_unknown_quantity_asks(syn):
    d = judge(syn, "900009", 10)
    assert d.context["quantityAttested"] is False and d.outcome is Outcome.ESCALATE


def test_placeholder_stock_marked_and_strict_switch(syn, monkeypatch):
    cat, _ = syn
    _, a = live(syn, "900002")
    f = quantity_fact(a["900002"], cat.get("900002"))
    assert f.level is TrustLevel.ATTESTED
    assert f.note == "Valio reports 9999999999, a placeholder, not a real count; treated as in stock"
    assert judge(syn, "900002", 100).outcome is Outcome.ALLOW
    monkeypatch.setenv("STRICT_PLACEHOLDER_STOCK", "1")
    assert judge(syn, "900002", 100).outcome is Outcome.ESCALATE


def test_listed_substitute_needs_the_pass(syn):
    assert judge(syn, "900006", 2, is_substitute=True, on_valio_list=True).outcome is Outcome.ALLOW
    none = replace(PASS, substitutes="none")
    assert judge(syn, "900006", 2, mandate=none, is_substitute=True, on_valio_list=True).outcome \
        is Outcome.ESCALATE


def test_split_fill_and_its_hard_lines(syn):
    cat, _ = syn
    q, a = live(syn, "900005", "900006", "900007")
    plan = plan_split(cat.get("900005"), 14, {"FREE_FROM_LACTOSE"}, cat, q, a, 500)
    assert [(x.product.id, x.sales_qty) for x in plan.parts] == [("900005", 10), ("900006", 2)]
    assert (plan.base_cents, plan.total_cents) == (14000, 14080)
    assert decide_split(plan, PASS, NOW, deliver_by=MON).outcome is Outcome.ALLOW
    no_split = replace(PASS, split_allow_listed=False)
    assert decide_split(plan, no_split, NOW, deliver_by=MON).outcome is Outcome.ESCALATE


def test_split_refuses_a_substitute_that_breaks_the_diet(syn):
    cat, _ = syn
    q, a = live(syn, "900005", "900006", "900007")
    a["900006"] = replace(a["900006"], lines=[])  # the good substitute cannot come, the next one has lactose
    plan = plan_split(cat.get("900005"), 14, {"FREE_FROM_LACTOSE"}, cat, q, a, 500)
    assert plan.needs_person
    assert [p.id for p, _ in plan.refused] == ["900007"]


@pytest.fixture
def svc(syn, tmp_path):
    cat, valio = syn
    return OrderService(Store(tmp_path / "orders.db"), cat, valio, AuditLog(tmp_path / "ledger.db"),
                        clock=lambda: NOW)


def test_order_placed_alone_and_logged(svc):
    o = svc.submit(mandate=PASS, lines=[LineIn("900001", 100)], deliver_by=MON, idempotency_key="s1")
    assert o["state"] == "placed" and o["totalCents"] == 10000
    (entry,) = [e for e in svc.audit.list(order_id=o["id"]) if e.kind == "order"]
    assert entry.sentence.startswith("Ordered 100 ST of 900001 SYNTHETIC")
    assert svc.audit.verify().ok


def test_placeholder_named_in_the_ledger(svc):
    o = svc.submit(mandate=PASS, lines=[LineIn("900002", 100)], deliver_by=MON, idempotency_key="s2")
    (entry,) = [e for e in svc.audit.list(order_id=o["id"]) if e.kind == "order"]
    assert entry.sentence.endswith("Valio reports 9999999999 for 900002, a placeholder, not a real count; "
                                   "treated as in stock.")


def test_short_in_boxes_never_approved(svc):
    o = svc.submit(mandate=PASS, lines=[LineIn("900004", 10)], deliver_by=MON, idempotency_key="s3",
                   required_claims=())
    assert o["state"] == "waiting"
    assert o["lines"][0]["short"] == "Only 3 KI of 900004 in stock, 10 needed"
    with pytest.raises(ApproveRefused, match="Only 3 KI of 900004 in stock, 10 needed"):
        svc.approve(o["id"], "owner:synthetic")


def test_waiting_order_approved_after_asking_again(svc):
    o = svc.submit(mandate=PASS, lines=[LineIn("900001", 1500)], deliver_by=MON, idempotency_key="s4")
    assert o["state"] == "waiting"  # 1500.00 EUR is over the auto limit, under the hard cap
    assert svc.approve(o["id"], "owner:synthetic")["state"] == "placed"
    with pytest.raises(Exception, match="only a waiting order"):
        svc.approve(o["id"], "owner:synthetic")
    assert svc.audit.verify().ok
