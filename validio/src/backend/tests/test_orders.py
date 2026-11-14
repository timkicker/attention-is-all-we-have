"""Step 8, order service: Validio re-asks Valio for every number, a retry orders once,
a placed order cannot be approved again. Numbers from the blueprint (scene 2, 462921, 463383)."""

from dataclasses import replace
from datetime import date, datetime

import pytest

from validio.audit.log import AuditLog
from validio.orders.service import (
    ApproveRefused,
    IdempotencyConflict,
    LineIn,
    OrderService,
    OrderStateError,
)
from validio.orders.store import Store
from validio.valio.models import Quote

NOW = datetime.fromisoformat("2026-11-14T10:00:00+02:00")
MON = date(2026, 11, 16)


@pytest.fixture(scope="module")
def valio():
    from validio.config import load_settings
    from validio.valio.client import ValioClient

    s = load_settings()
    if not any(s.valio_cache.glob("price/*/*.json")):
        pytest.skip("needs_data: no recorded Valio answers, run make record")
    return ValioClient(s.valio_base_url, "", "replay", s.valio_cache)


@pytest.fixture(scope="module")
def mandate():
    from jwcrypto.jwk import JWK

    from validio.policy.mandate import (
        AUDIENCE,
        DEMO_CLAIMS,
        DEMO_SD_FIELDS,
        NonceStore,
        issue_mandate,
        present,
        verify_presentation,
    )

    kitchen, agent = JWK.generate(kty="EC", crv="P-256"), JWK.generate(kty="EC", crv="P-256")
    nonces = NonceStore()
    token = present(issue_mandate(DEMO_CLAIMS, DEMO_SD_FIELDS, kitchen, agent),
                    {"autoLimitCents", "hardCapCents", "diet"}, agent, AUDIENCE, nonces.issue(NOW), iat=int(NOW.timestamp()))
    return verify_presentation(token, kitchen_pub=kitchen, issuer="kitchen:hotel-espoo", aud=AUDIENCE,
                               nonces=nonces, now=NOW)


class PriceUp:
    """The recorded Valio answers with every price raised by `pct`, as if Valio changed it meanwhile."""

    def __init__(self, inner, pct: float):
        self.inner, self.pct = inner, pct

    def price(self, ids, requested, budget):
        out = self.inner.price(ids, requested, budget)
        return {k: replace(q, price_cents=round(q.price_cents * (1 + self.pct / 100)))
                if isinstance(q, Quote) and q.price_cents else q for k, q in out.items()}

    def availability(self, ids, requested, budget):
        return self.inner.availability(ids, requested, budget)


@pytest.fixture
def svc(tmp_path, catalog, valio):
    store = Store(tmp_path / "validio.db")
    return OrderService(store, catalog, valio, AuditLog(tmp_path / "validio.db"), clock=lambda: NOW)


def milk(qty=1000, **kw):
    return [LineIn(product_id="464306", sales_qty=qty, **kw)]


def mozz_swap():
    # 463383 grated mozzarella from outside Valio's list: 10 bags = 25 kg
    return [LineIn(product_id="463383", sales_qty=10, is_substitute=True, on_valio_list=False)]


def test_allow_goes_to_placed(svc, mandate):
    o = svc.submit(mandate=mandate, lines=milk(), deliver_by=MON, idempotency_key="k1")
    assert o["state"] == "placed"
    assert o["totalCents"] == 101000
    assert o["decision"]["outcome"] == "auto_order"
    assert [h["state"] for h in o["history"]] == ["placed"]


def test_escalate_waits_for_human(svc, mandate):
    o = svc.submit(mandate=mandate, lines=mozz_swap(), deliver_by=MON, idempotency_key="k2")
    assert o["state"] == "waiting"
    assert o["totalCents"] == 19660
    assert o["decision"]["outcome"] == "ask_human"
    assert "not on Valio's list" in o["decision"]["sentence"]


def test_deny_is_blocked_with_sentence(svc, mandate):
    # 462921 Eila organic: 200 KI at 10.97 EUR = 2194.00 EUR, over the 2000 EUR hard cap
    o = svc.submit(mandate=mandate, lines=[LineIn(product_id="462921", sales_qty=200)], deliver_by=MON,
                   idempotency_key="k3")
    assert o["state"] == "blocked"
    assert o["totalCents"] == 219400
    assert "never-over-hard-cap" in o["decision"]["ruleIds"]
    assert "hard cap" in o["decision"]["sentence"]


def test_idempotent_submit(svc, mandate):
    a = svc.submit(mandate=mandate, lines=milk(), deliver_by=MON, idempotency_key="same")
    b = svc.submit(mandate=mandate, lines=milk(), deliver_by=MON, idempotency_key="same")
    assert a["id"] == b["id"]
    assert len(svc.store.orders()) == 1
    assert len([e for e in svc.audit.list() if e.kind == "order"]) == 1


def test_same_key_other_body_is_refused(svc, mandate):
    svc.submit(mandate=mandate, lines=milk(), deliver_by=MON, idempotency_key="same")
    with pytest.raises(IdempotencyConflict):
        svc.submit(mandate=mandate, lines=milk(999), deliver_by=MON, idempotency_key="same")


def test_proposal_price_ignored(svc, mandate):
    # the agent claims 1 cent per carton, Validio asks Valio and uses 1.01 EUR
    o = svc.submit(mandate=mandate, lines=milk(proposed_price_cents=1), deliver_by=MON, idempotency_key="k4")
    assert o["lines"][0]["priceCents"] == 101
    assert o["totalCents"] == 101000
    assert "proposedPriceCents" not in str(o)


def test_approve_places_after_requote(svc, mandate):
    o = svc.submit(mandate=mandate, lines=mozz_swap(), deliver_by=MON, idempotency_key="k5")
    done = svc.approve(o["id"], approver="owner")
    assert done["state"] == "placed"
    assert [h["state"] for h in done["history"]] == ["waiting", "approved", "placed"]
    kinds = [e.kind for e in svc.audit.list(order_id=o["id"])]
    assert kinds == ["decision", "approval", "order"]


def test_cannot_approve_placed_order(svc, mandate):
    auto = svc.submit(mandate=mandate, lines=milk(), deliver_by=MON, idempotency_key="k7")  # first: M-1 is empty
    with pytest.raises(OrderStateError):
        svc.approve(auto["id"], approver="owner")
    o = svc.submit(mandate=mandate, lines=mozz_swap(), deliver_by=MON, idempotency_key="k6")
    svc.approve(o["id"], approver="owner")
    with pytest.raises(OrderStateError):
        svc.approve(o["id"], approver="owner")


def test_approve_requotes_and_refuses_price_rise(svc, mandate):
    o = svc.submit(mandate=mandate, lines=mozz_swap(), deliver_by=MON, idempotency_key="k8")
    svc.valio = PriceUp(svc.valio, 3)
    with pytest.raises(ApproveRefused, match="price"):
        svc.approve(o["id"], approver="owner")
    assert svc.get(o["id"])["state"] == "waiting"


def test_approve_accepts_small_price_rise(svc, mandate):
    o = svc.submit(mandate=mandate, lines=mozz_swap(), deliver_by=MON, idempotency_key="k9")
    svc.valio = PriceUp(svc.valio, 1.5)
    assert svc.approve(o["id"], approver="owner")["state"] == "placed"


def test_reject(svc, mandate):
    o = svc.submit(mandate=mandate, lines=mozz_swap(), deliver_by=MON, idempotency_key="k10")
    r = svc.reject(o["id"], approver="owner", reason="we want fresh balls")
    assert r["state"] == "rejected"
    with pytest.raises(OrderStateError):
        svc.approve(o["id"], approver="owner")


def test_order_with_two_lines(svc, mandate):
    lines = milk(300) + [LineIn(product_id="464401", sales_qty=100)]
    o = svc.submit(mandate=mandate, lines=lines, deliver_by=MON, idempotency_key="k11")
    assert [ln["productId"] for ln in o["lines"]] == ["464306", "464401"]
    assert o["totalCents"] == 300 * 101 + 100 * 110
    assert o["state"] == "placed"


def test_short_stock_never_orders_alone(svc, mandate):
    o = svc.submit(mandate=mandate, lines=milk(), deliver_by=MON, idempotency_key="k12",
                   stock_override={"464306": 0})
    assert o["state"] != "placed"


def test_scene2_ledger_sentence(svc, mandate):
    o = svc.submit(mandate=mandate, lines=milk(), deliver_by=MON, idempotency_key="k13")
    (entry,) = [e for e in svc.audit.list(order_id=o["id"]) if e.kind == "order"]
    assert entry.sentence.startswith("Ordered 1,000 packs of Valio Hyvä suomalainen Arki Eila ")
    assert "for 1,010.00 € without a person. Valio attests the stock and the contract price until " \
           "31 Dec 2026, delivery 16 Nov. Inside Spend Pass M-1, whose disclosed auto limit is 1,200.00 €." \
           in entry.sentence
    assert entry.rule_ids == ["auto-order"]
    assert "approvers" not in entry.disclosed
    assert svc.audit.verify().ok


def test_split_order_with_line_diet_is_placed_alone(svc, mandate):
    # Steady Order parmesan: the line has no diet of its own, the split is 2.5 % over the 754.00 base
    lines = [LineIn("463968", 137), LineIn("469648", 40, is_substitute=True, on_valio_list=True)]
    o = svc.submit(mandate=mandate, lines=lines, deliver_by=MON, idempotency_key="parm",
                   required_claims=(), split_base_cents=75400)
    assert o["state"] == "placed" and o["totalCents"] == 77249
    assert o["requiredClaims"] == [] and o["splitBaseCents"] == 75400


def test_line_diet_defaults_to_the_pass_diet(svc, mandate):
    lines = [LineIn("463968", 137), LineIn("469648", 40, is_substitute=True, on_valio_list=True)]
    o = svc.submit(mandate=mandate, lines=lines, deliver_by=MON, idempotency_key="parm2")
    assert o["state"] == "waiting"  # parmesan claims nothing about lactose, so under the pass diet a person looks


def test_approve_keeps_the_line_diet(svc, mandate):
    o = svc.submit(mandate=mandate, lines=[LineIn("466375", 98)], deliver_by=MON, idempotency_key="mozz",
                   required_claims=("FREE_FROM_LACTOSE",))
    assert o["state"] == "waiting"  # lactose claim unchecked
    assert svc.approve(o["id"], "owner:anna")["state"] == "placed"


def test_placeholder_stock_shown_in_facts_and_ledger(svc, mandate, monkeypatch):
    monkeypatch.delenv("STRICT_PLACEHOLDER_STOCK", raising=False)
    o = svc.submit(mandate=mandate, lines=milk(), deliver_by=MON, idempotency_key="k-placeholder")
    assert o["state"] == "placed"
    (q,) = [f for f in o["lines"][0]["facts"] if f["field"] == "quantity"]
    assert q["grade"] == "attested"
    assert q["note"] == "Valio reports 9999999999, a placeholder, not a real count; treated as in stock"
    (entry,) = [e for e in svc.audit.list(order_id=o["id"]) if e.kind == "order"]
    assert entry.sentence.endswith(" Valio gives no real count of the stock, so Validio treats it as in stock.")
    assert "9999999999" not in entry.sentence
    assert svc.audit.verify().ok


def test_short_in_sales_units_refuses_approve(svc, mandate):
    # review-3 H4: Valio has 36 ST of 469054, which is 3 cartons of 12. 10 cartons must never be placed.
    o = svc.submit(mandate=mandate, lines=[LineIn("469054", 10)], deliver_by=MON, idempotency_key="h4",
                   required_claims=())
    assert o["lines"][0]["short"] == "Only 3 cartons of Valio old style fermented milk 190 g low lacotse in stock, 10 needed"
    assert o["lines"][0]["deliverable"] is False
    assert o["state"] == "waiting"
    with pytest.raises(ApproveRefused, match="Only 3 cartons of Valio old style fermented milk 190 g low lacotse in stock, 10 needed"):
        svc.approve(o["id"], "owner:anna")
    assert svc.get(o["id"])["state"] == "waiting"
    ok = svc.submit(mandate=mandate, lines=[LineIn("469054", 3)], deliver_by=MON, idempotency_key="h4-ok",
                    required_claims=())
    assert ok["lines"][0]["short"] is None  # control: 3 cartons are there


def test_short_line_keeps_valio_answer_for_the_hard_lines(svc, mandate):
    # L3: a short line goes to Cedar with Valio's real answer, so it asks a person instead of looking undeliverable
    o = svc.submit(mandate=mandate, lines=[LineIn("469054", 10)], deliver_by=MON, idempotency_key="l3",
                   required_claims=())
    assert o["state"] == "waiting"
    assert "Valio does not confirm enough stock" in o["decision"]["sentence"]


# review 3 M1: the limits of a Spend Pass hold across its orders, not per order

def test_running_total_makes_the_second_order_wait(svc, mandate):
    assert svc.submit(mandate=mandate, lines=milk(), deliver_by=MON, idempotency_key="r1")["state"] == "placed"
    o = svc.submit(mandate=mandate, lines=milk(300), deliver_by=MON, idempotency_key="r2")
    assert o["totalCents"] == 30300  # the order itself stays what it costs
    assert o["state"] == "waiting", o["decision"]
    s = o["decision"]["sentence"]
    assert "Spend Pass M-1 already placed 1,010.00 €" in s and "1,313.00 €" in s


def test_running_total_over_the_hard_cap_blocks(svc, mandate):
    svc.submit(mandate=mandate, lines=milk(), deliver_by=MON, idempotency_key="r1")
    o = svc.submit(mandate=mandate, lines=milk(), deliver_by=MON, idempotency_key="r2")
    assert o["state"] == "blocked" and "never-over-hard-cap" in o["decision"]["ruleIds"]


def test_running_total_counts_placed_orders_of_this_pass_only(svc, mandate):
    assert svc.submit(mandate=mandate, lines=mozz_swap(), deliver_by=MON, idempotency_key="r0")["state"] == "waiting"
    assert svc.submit(mandate=mandate, lines=milk(), deliver_by=MON, idempotency_key="r1")["state"] == "placed"
    other = replace(mandate, id="M-2")
    assert svc.submit(mandate=other, lines=milk(300), deliver_by=MON, idempotency_key="r2")["state"] == "placed"


def test_approve_counts_what_was_placed_meanwhile(svc, mandate):
    swap = svc.submit(mandate=mandate, lines=mozz_swap(), deliver_by=MON, idempotency_key="r0")  # 196.60 waits
    svc.submit(mandate=mandate, lines=milk(), deliver_by=MON, idempotency_key="r1")  # 1010.00 placed
    big = svc.submit(mandate=mandate, lines=milk(800), deliver_by=MON, idempotency_key="r2")  # 1818.00 waits
    assert svc.approve(big["id"], "owner")["state"] == "placed"
    with pytest.raises(ApproveRefused, match="hard cap"):  # 1818.00 + 196.60 is over 2000.00
        svc.approve(swap["id"], "owner")
    assert svc.get(swap["id"])["state"] == "waiting"
