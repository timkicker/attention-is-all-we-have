"""Steady Orders: what a kitchen ordered before, what it usually orders, and what Drift Watch found."""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Any


@dataclass(frozen=True)
class PastOrder:
    """One week's delivered order. The demo history is simulated and says so."""

    delivered: date
    guests: int
    lines: dict[str, int]  # product id to sales units
    simulated: bool
    unit_cents: dict[str, int] = field(default_factory=dict)  # price paid, empty means the price stayed flat

    def qty(self, product_id: str) -> int:
        return self.lines.get(product_id, 0)


@dataclass(frozen=True)
class History:
    kitchen: str
    weekday: int  # 0 is Monday
    diet: dict[str, tuple[str, ...]]  # per line, the claims the kitchen needs kept
    weeks: list[PastOrder]
    simulated: bool
    note: str = ""

    @property
    def product_ids(self) -> list[str]:
        return list(self.diet)


@dataclass(frozen=True)
class StandingLine:
    product_id: str
    sales_qty: int  # the median of the weeks learned from
    per_guest: float
    diet: tuple[str, ...]  # claims this line must keep, e.g. gluten free and vegan for the pancakes


@dataclass(frozen=True)
class StandingOrder:
    id: str
    kitchen: str
    name: str
    weekday: int
    lines: list[StandingLine]
    guests: int
    learned_from: int  # weeks of history
    simulated: bool  # the history behind it is simulated


class DriftKind(StrEnum):
    PER_GUEST_UP = "per_guest_up"  # the last 2 weeks are more than 20 % over the first 4, per guest
    COST_UP = "cost_up"  # this week's line cost is more than 10 % over the median
    CONTRACT_ENDS = "contract_ends"  # the price ends before the next 4 renewals
    STOCK_BELOW = "stock_below"  # Valio has less in stock than the usual line


@dataclass(frozen=True)
class DriftFlag:
    kind: DriftKind
    product_id: str
    sentence: str
    value: float  # the measured value: ratio, cents, days or stock
    pct: int | None = None


class LineResult(StrEnum):
    RENEWED = "renewed"  # through the normal pipeline, ordered automatically
    SPLIT_RENEWED = "split_renewed"  # Split Fill kept every rule, ordered automatically
    WAITING = "waiting"  # Hard Lines or a split that breaks a rule ask a person
    FLAGGED = "flagged"  # Drift Watch flagged it, a person decides
    BLOCKED = "blocked"  # a Hard Line forbids it, not even a person can let it through
    ACCEPTED = "accepted"  # a person let a waiting or flagged line through


@dataclass(frozen=True)
class RenewedLine:
    product_id: str
    usual_qty: int
    this_week_qty: int | None
    total_cents: int | None
    result: LineResult
    sentence: str
    flags: list[DriftFlag]
    decision: Any = None  # policy.decide.Decision
    split: Any = None  # the Split Fill plan when the line was split
    accept_label: str | None = None
    accepted_by: str | None = None


@dataclass(frozen=True)
class Renewal:
    order_id: str
    at: datetime
    delivery: date
    lines: list[RenewedLine]
    simulated_history: bool
