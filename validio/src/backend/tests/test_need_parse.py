"""parse_need without the catalog: numbers as people write them. Runs without Valio's data."""

from datetime import date

import pytest

from validio.matching.need import number, parse_need

SAT = date(2026, 11, 14)


@pytest.mark.parametrize("written, value", [
    ("1000", 1000), ("1,000", 1000), ("1.000", 1000), ("1 000", 1000), ("1 000", 1000), ("10,000", 10000),
    ("2,5", 2.5), ("1.5", 1.5), ("12,34", 12.34), ("1,000.50", 1000.5), ("1.000,50", 1000.5),
])
def test_numbers_as_people_write_them(written, value):
    assert number(written) == value


@pytest.mark.parametrize("text", ["1,000 litres of lactose-free milk", "1.000 litres of lactose-free milk",
                                  "1 000 litres of lactose-free milk", "1000 litres of lactose-free milk"])
def test_thousands_are_never_read_as_one_litre(text):
    n = parse_need(text + " by Monday, budget 1,200 euro", SAT)
    assert (n.quantity, n.unit, n.budget_cents) == (1000, "L", 120000)


def test_decimal_comma_stays_a_decimal():
    assert parse_need("2,5 kg of mozzarella", SAT).quantity == 2.5


@pytest.mark.parametrize("text", ["0 litres of milk", "0,0 kg of mozzarella"])
def test_zero_quantity_is_refused(text):
    with pytest.raises(ValueError, match="not more than zero"):
        parse_need(text, SAT)
