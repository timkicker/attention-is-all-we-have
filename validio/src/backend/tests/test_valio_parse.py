"""Valio's answers read strictly: odd shapes are refused as an outage, never a 500 or a guess. No data needed."""

from datetime import date

import httpx
import pytest

from validio.valio.budget import CallBudget
from validio.valio.client import ValioClient, ValioMalformed
from validio.valio.models import Availability, _cents

DAY = date(2026, 11, 16)


def client(handler) -> ValioClient:
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return ValioClient("https://junction26.valioaimo.fi", "k", "live", None, http=http, backoff=0)


@pytest.mark.parametrize("body", [{"nope": []}, {"products": [{"catalogPrice": {"value": 1}}]},
                                  {"products": [{"productId": "1", "catalogPrice": {"value": "abc"}}]}, ["x"]])
def test_an_unreadable_price_answer_is_valio_malformed(body):
    v = client(lambda req: httpx.Response(200, json=body))
    with pytest.raises(ValioMalformed, match="cannot read"):
        v.price(["1"], DAY, CallBudget())


def test_a_non_json_answer_is_valio_malformed():
    v = client(lambda req: httpx.Response(200, text="<html>maintenance</html>"))
    with pytest.raises(ValioMalformed):
        v.availability(["1"], DAY, CallBudget())


def test_times_with_fractions_colons_or_z_are_read():
    for closing in ("2026-11-15T12:00:00+0200", "2026-11-15T12:00:00.250+02:00", "2026-11-15T10:00:00Z"):
        a = Availability.from_api({"productId": "1", "closingTime": closing, "scheduleLines": []}, None)
        assert a.closing_time.utcoffset() is not None


def test_schedule_lines_are_read_earliest_first():
    a = Availability.from_api({"productId": "1", "scheduleLines": [
        {"availableAmount": 5, "availableDate": "2026-11-18", "salesUnit": "ST"},
        {"availableAmount": 9, "availableDate": "2026-11-16", "salesUnit": "ST"}]}, None)
    assert a.lines[0].available == DAY and a.amount == 9


def test_money_is_rounded_half_up_from_the_decimal_valio_wrote():
    assert _cents({"value": 1.005}) == 101 and _cents({"value": 18.01}) == 1801 and _cents({"value": "2.5"}) == 250
