"""One sentence per decision, the way the ledger and the web app show it."""

from datetime import date

from ..text.format import money, qty_text, short_ref


def eur(cents: int) -> str:
    return money(cents)


def _day(iso: str, year: bool = False) -> str:
    d = date.fromisoformat(iso)
    return d.strftime("%d %b %Y" if year else "%d %b").lstrip("0")


def ordered_alone(
    *,
    quantity: int,
    unit: str,
    product_id: str,
    product_name: str,
    total_cents: int,
    price_valid_until: str,
    delivery_date: str,
    mandate_id: str,
    auto_limit_cents: int,
    qty: str | None = None,
) -> str:
    return (
        f"Ordered {(q := qty or qty_text(quantity, unit))} of {short_ref(product_name, with_size='×' not in q)} for {money(total_cents)} "
        f"without a person. Valio attests the stock and the contract price until "
        f"{_day(price_valid_until, year=True)}, delivery {_day(delivery_date)}. "
        f"Inside Spend Pass {mandate_id}, whose disclosed auto limit is {money(auto_limit_cents)}."
    )
