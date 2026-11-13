"""One sentence per decision, the way the ledger and the web app show it."""

from datetime import date

from ..text.format import display_name, money, qty_text


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
) -> str:
    return (
        f"Ordered {qty_text(quantity, unit)} of {display_name(product_name)} ({product_id}) for {money(total_cents)} "
        f"without a person. Valio attests the stock and the contract price until "
        f"{_day(price_valid_until, year=True)}, delivery {_day(delivery_date)}. "
        f"Inside Spend Pass {mandate_id}, whose disclosed auto limit is {money(auto_limit_cents)}."
    )
