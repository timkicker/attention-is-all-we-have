from dataclasses import dataclass
from datetime import date, datetime

NO_END = date(9999, 12, 31)


def _cents(price: dict | None) -> int | None:
    return None if not price or price.get("value") is None else round(price["value"] * 100)


def _ts(s: str | None) -> datetime | None:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S%z") if s else None


@dataclass(frozen=True)
class Quote:
    product_id: str
    error: bool
    price_cents: int | None  # catalogPrice, per sales unit, before tax
    valid_to: date | None  # None when the price has no end date
    net_price_found: bool
    list_price_cents: int | None
    comparison_price_cents: int | None
    comparison_unit: str | None
    tax_rate: float | None

    @classmethod
    def from_api(cls, x: dict) -> "Quote":
        cp = x.get("catalogPrice") or {}
        vt = _ts(cp.get("validTo"))
        return cls(
            product_id=x["productId"], error=bool(x.get("error")), price_cents=_cents(cp or None),
            valid_to=None if vt is None or vt.date() >= NO_END else vt.date(),
            net_price_found=bool(x.get("netPriceFound")), list_price_cents=_cents(x.get("listPrice")),
            comparison_price_cents=_cents(x.get("comparisonPrice")), comparison_unit=x.get("comparisonUnit"),
            tax_rate=(x.get("tax") or {}).get("taxRate"),
        )


@dataclass(frozen=True)
class ScheduleLine:
    amount: float
    available: date
    sales_unit: str
    sales_block: bool


@dataclass(frozen=True)
class Availability:
    product_id: str
    logistic_model: str | None  # Stock (Valio's warehouse) or Terminal (at the supplier)
    closing_time: datetime | None  # order cut-off
    sales_block: bool
    lines: list[ScheduleLine]
    time_now: datetime | None

    @property
    def deliverable(self) -> bool:
        return bool(self.lines) and not self.sales_block and not any(ln.sales_block for ln in self.lines)

    @property
    def amount(self) -> float | None:
        return self.lines[0].amount if self.lines else None

    @classmethod
    def from_api(cls, x: dict, time_now: str | None) -> "Availability":
        return cls(
            product_id=x["productId"], logistic_model=x.get("logisticModel"),
            closing_time=_ts(x.get("closingTime")), sales_block=bool(x.get("salesBlock")),
            lines=[ScheduleLine(amount=ln["availableAmount"], available=date.fromisoformat(ln["availableDate"]),
                                sales_unit=ln["salesUnit"], sales_block=bool(ln.get("salesBlock")))
                   for ln in x.get("scheduleLines") or [] if ln.get("availableDate")],  # none: no date given
            time_now=_ts(time_now),
        )
