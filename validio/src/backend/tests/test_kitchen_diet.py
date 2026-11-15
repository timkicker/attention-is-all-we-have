"""A diet the kitchen signed into its Spend Pass is not a diet the agent typed. "lactose-free milk" in the text
screens out every milk without the claim. The kitchen-wide lactose-free rule only grades: a product Valio's data
says nothing about (bananas carry no claims at all) stays a candidate and waits for the owner, because a missing
value is never a yes; a product whose own data says otherwise is still blocked.

Valio's answers here are invented (price 4.00 EUR, 500 in stock), so the test needs no recording for products
the demo scenes never touch. Only the catalog is Valio's."""

from datetime import date, datetime

import pytest

from validio.audit.log import AuditLog
from validio.orders.service import OrderService
from validio.orders.store import Store
from validio.orders.supply import LineRequest, SupplyService
from validio.valio.models import Availability, Quote

NOW = datetime.fromisoformat("2026-11-14T10:00:00+02:00")
MON = date(2026, 11, 16)
BANANA = "461010"  # BANANA 4.5KG GT/CR, fresh produce, no claims and no allergen data
ROQUEFORT = "460426"  # lists milk, no lactose-free claim, no lactose value
SALAD_CHEESE = "460217"  # lists lactose, 6.3 g per 100 g


class Invented:
    """Answers every id the way Valio's test API would, with made-up numbers."""

    mode = "replay"

    def __init__(self, catalog):
        self.catalog, self.asked = catalog, []

    def recorded_days(self):
        return None

    def price(self, ids, requested, budget):
        budget.reserve(ids)
        budget.count_call(len(ids))
        self.asked += ids
        return {i: Quote.from_api({"productId": i, "error": False, "netPriceFound": True,
                                   "catalogPrice": {"value": 4.0, "validTo": "2026-12-31T23:59:59+0200"}})
                for i in ids}

    def availability(self, ids, requested, budget):
        budget.reserve(ids)
        budget.count_call(len(ids))
        out = {}
        for i in ids:
            unit = self.catalog.get(i).sales_unit
            out[i] = Availability.from_api({
                "productId": i, "logisticModel": "Stock", "closingTime": "2026-11-15T12:00:00+0200",
                "salesBlock": False, "scheduleLines": [{"availableAmount": 500.0, "availableDate": MON.isoformat(),
                                                        "salesUnit": unit, "salesBlock": False}]},
                "2026-11-14T10:00:00+0200")
        return out


@pytest.fixture(scope="module")
def mandate():
    """M-1 with fresh produce, baby food and cheese among its product groups, so only the diet decides."""
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

    claims = {**DEMO_CLAIMS, "categories": [*DEMO_CLAIMS["categories"], "174", "216"]}
    kitchen, agent = JWK.generate(kty="EC", crv="P-256"), JWK.generate(kty="EC", crv="P-256")
    nonces = NonceStore()
    token = present(issue_mandate(claims, DEMO_SD_FIELDS, kitchen, agent), {"autoLimitCents", "hardCapCents", "diet"},
                    agent, AUDIENCE, nonces.issue(NOW), iat=int(NOW.timestamp()))
    m = verify_presentation(token, kitchen_pub=kitchen, issuer="kitchen:hotel-espoo", aud=AUDIENCE, nonces=nonces,
                            now=NOW)
    assert m.diet == ("FREE_FROM_LACTOSE",)
    return m


@pytest.fixture
def supply(tmp_path, catalog):
    valio = Invented(catalog)
    svc = OrderService(Store(tmp_path / "validio.db"), catalog, valio, AuditLog(tmp_path / "validio.db"),
                       clock=lambda: NOW)
    return SupplyService(svc), valio


def ask(supply, mandate, line: LineRequest, key: str) -> dict:
    svc, _ = supply
    return svc.request_supply(mandate=mandate, lines=[line], deliver_by=MON, idempotency_key=key)


def test_bananas_by_id_wait_for_the_owner(supply, mandate):
    req = ask(supply, mandate, LineRequest(product_id=BANANA, quantity=10), "banana-id")
    assert req["status"] == "waiting", req["decision"]
    assert req["decision"]["reasonCode"] == "diet_unchecked"
    assert req["decision"]["ownerText"] == ("Waiting for you: Valio's data doesn't confirm it is lactose free, "
                                            "so you decide.")
    (line,) = req["lines"]
    assert line["chosen"]["productId"] == BANANA and req["totalCents"] == 4000
    (opt,) = [o for o in line["options"] if o["productId"] == BANANA]
    assert opt["verdict"] == "chosen" and "doesn't confirm it is lactose free" in opt["sentence"]


def test_bananas_by_text_wait_for_the_owner(supply, mandate):
    """The repro: a claimless product asked for in words under the kitchen's lactose-free rule."""
    req = ask(supply, mandate, LineRequest(text="10 packs of bananas 4.5 kg"), "banana-text")
    assert req["status"] == "waiting", req["decision"]
    assert req["decision"]["reasonCode"] == "diet_unchecked"
    assert "banana" in req["lines"][0]["options"][0]["name"].lower()


def test_a_product_that_lists_milk_is_blocked(supply, mandate):
    req = ask(supply, mandate, LineRequest(product_id=ROQUEFORT, quantity=5), "roquefort")
    assert req["status"] == "blocked", req["decision"]
    assert req["decision"]["reasonCode"] == "diet", req["decision"]
    assert req["decision"]["ownerText"] == "Not ordered: Valio's own data doesn't show it is lactose free."
    (opt,) = req["lines"][0]["options"]
    assert opt["verdict"] == "rejected" and "Lists milk and has no lactose-free claim" in opt["sentence"]


def test_a_product_with_lactose_is_blocked_by_cedar(supply, mandate):
    req = ask(supply, mandate, LineRequest(product_id=SALAD_CHEESE, quantity=5), "salad-cheese")
    assert req["status"] == "blocked", req["decision"]
    assert req["decision"]["reasonCode"] == "diet", req["decision"]
    (opt,) = req["lines"][0]["options"]
    assert opt["verdict"] == "blocked" and "a diet rule of the Spend Pass is contradicted" in opt["sentence"]


def test_lactose_free_in_the_text_still_screens_out_claimless_milk(supply, mandate, catalog):
    from validio.matching.need import parse_need, screen

    _, valio = supply
    req = ask(supply, mandate, LineRequest(text="100 litres of lactose-free milk by Monday"), "lf-milk")
    shown = [catalog.get(o["productId"]) for o in req["lines"][0]["options"]]
    assert shown and all("FREE_FROM_LACTOSE" in p.claims or "LOW_LACTOSE" in p.claims
                         or "lactose" in p.name_en.lower() for p in shown)
    assert all("FREE_FROM_LACTOSE" in catalog.get(i).claims for i in valio.asked)
    # the same words without "lactose-free": the kitchen's rule keeps a claimless milk a candidate
    need = parse_need("100 litres of milk by Monday", MON, catalog)
    need.kitchen_claims = {"FREE_FROM_LACTOSE"}
    need.required_claims |= need.kitchen_claims
    assert need.strict_claims == set()
    strict = parse_need("100 litres of lactose-free milk by Monday", MON, catalog)
    assert strict.strict_claims == {"FREE_FROM_LACTOSE"}
    assert {p.id for p in screen(strict, catalog)[0]} <= {p.id for p in screen(need, catalog, limit=None)[0]}


def test_kitchen_diet_drops_only_what_the_data_contradicts(catalog):
    from validio.matching.need import kitchen_break

    assert kitchen_break(catalog.get(BANANA), "FREE_FROM_LACTOSE") is None
    assert kitchen_break(catalog.get(ROQUEFORT), "FREE_FROM_LACTOSE") == \
        "Lists milk and has no lactose-free claim in Valio's data"
    assert kitchen_break(catalog.get(SALAD_CHEESE), "FREE_FROM_LACTOSE").startswith("Not lactose free: ")
