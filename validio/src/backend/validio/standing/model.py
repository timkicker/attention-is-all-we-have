"""Steady Orders: what a kitchen ordered before, what it usually orders, and what Drift Watch found."""

from dataclasses import dataclass, field
from datetime import date


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
