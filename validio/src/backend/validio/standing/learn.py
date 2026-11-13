"""Learn the usual weekly order from at least 4 weeks of history: the median per line and guests per week."""

import math
from statistics import median

from .model import History, StandingLine, StandingOrder

MIN_WEEKS = 4


class NotEnoughHistory(ValueError):
    pass


def learn(history: History, min_weeks: int = MIN_WEEKS, order_id: str = "S-1",
          name: str = "Weekly Monday order") -> StandingOrder:
    weeks = history.weeks
    if len(weeks) < min_weeks:
        raise NotEnoughHistory(f"a Steady Order needs {min_weeks} weeks of history, there are {len(weeks)}")
    guests = math.ceil(median(w.guests for w in weeks))
    lines = []
    for pid in history.product_ids:
        qty = math.ceil(median(w.qty(pid) for w in weeks))  # half a pack rounds up
        lines.append(StandingLine(pid, qty, qty / guests if guests else 0.0, history.diet[pid]))
    return StandingOrder(order_id, history.kitchen, name, history.weekday, lines, guests, len(weeks),
                         history.simulated)
