"""One sentence per decision, the way the ledger and the web app show it."""

from datetime import date


def eur(cents: int) -> str:
    return f"{cents // 100}.{cents % 100:02d} EUR"


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
        f"Ordered {quantity} {unit} of {product_id} {product_name} for {eur(total_cents)} without a human. "
        f"Stock quantity attested by Valio, contract price until {_day(price_valid_until, year=True)}, "
        f"delivery {_day(delivery_date)}. "
        f"Inside mandate {mandate_id} (auto limit disclosed: {eur(auto_limit_cents)})."
    )
