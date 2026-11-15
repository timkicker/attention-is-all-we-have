"""Rerun 5: a turned-down row names the rule it breaks, and a line with no product at all says so plainly.
The recorded Valio answers hold no butter, so the butter cases live on as unit tests of the wording only."""

from asking import ask as agent_asks
from test_api import client  # noqa: F401

from validio.api.display import group, short_text


def ask(client, text):  # noqa: F811
    """The kitchen's agent asks over MCP; the request as the web app reads it."""
    from validio.api.state import get_ctx

    rid = agent_asks(get_ctx(), text).request_id
    assert rid, f"no request for {text!r}"
    return client.get(f"/api/requests/{rid}").json()


def test_outside_the_product_groups_is_named():
    r = ["Cheapest safe option.", "Blocked: it is outside the Spend Pass's product groups."]
    assert group(r)[0] == "Outside the pass's product groups"
    assert short_text("blocked", r) == "Outside the pass's product groups."


def test_no_lactose_free_parmesan_is_one_plain_reason(client):  # noqa: F811
    # the text asks for lactose-free, so a parmesan without the claim is no candidate at all
    req = ask(client, "20 kg of lactose-free parmesan by Monday")
    assert req["status"] == "blocked"
    assert req["decision"]["sentence"] == "Valio has no lactose-free parmesan. Nothing was ordered."


def test_lactose_free_oat_drink_names_its_leading_reason(client):  # noqa: F811
    req = ask(client, "200 litres of lactose-free oat drink by Monday")
    # plain oat drinks carry no lactose-free claim, so none is a candidate when the text asks for it
    assert req["decision"]["sentence"] == "Valio has no lactose-free oat drink. Nothing was ordered."


def test_under_the_kitchen_diet_plain_oat_drinks_stay_and_flavours_are_hidden(catalog):
    """M-1's lactose-free rule is the kitchen's, not the text's: oat drinks Valio's data is silent on stay
    candidates (a person decides), the flavoured ones are still another product."""
    from datetime import date

    from validio.matching.need import parse_need, screen

    need = parse_need("200 litres of oat drink by Monday", date(2026, 11, 14), catalog)
    need.kitchen_claims = {"FREE_FROM_LACTOSE"}
    need.required_claims |= need.kitchen_claims
    kept, dropped = screen(need, catalog)
    names = [p.name_en.lower() for p in kept] + [r.product.name_en.lower() for r in dropped]
    assert kept and not any("cookie" in n or "chocolate" in n or "vanilla" in n for n in names)


def test_without_the_diet_flavoured_oat_drinks_are_not_candidates(catalog):
    from datetime import date

    from validio.matching.need import parse_need, screen

    kept, dropped = screen(parse_need("200 litres of oat drink by Monday", date(2026, 11, 14), catalog), catalog)
    names = [p.name_en.lower() for p in kept] + [r.product.name_en.lower() for r in dropped]
    assert kept and not any("cookie" in n or "chocolate" in n for n in names)


def test_over_the_cap_names_amount_and_cap(client):  # noqa: F811
    import re

    req = ask(client, "3000 litres of lactose-free milk by Monday")
    s = req["decision"]["sentence"]
    m = re.fullmatch(r"Blocked: ([\d,.]+) € is over the 2,000\.00 € never-above limit\. Nothing was ordered\.", s)
    assert m, s
    cheapest = min(o["totalCents"] for ln in req["lines"] for o in ln["options"]
                   if "over the hard cap" in o["sentence"])
    assert m.group(1) == f"{cheapest / 100:,.2f}"
