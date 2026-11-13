"""One read-only pass against Valio's test API: price and availability for every product id
the five demo scenes touch, stored under data/cache/valio/ for replay. 40 ids per HTTP call.
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "backend"))
from validio.catalog.store import Catalog
from validio.config import load_settings
from validio.valio.budget import CallBudget
from validio.valio.client import ValioClient

MONDAY = date(2026, 11, 16)
SCENE_IDS = [
    # scene 2, milk
    "464306", "464401", "463038", "462921", "462703", "463047", "469541", "469363",
    # scene 3, mozzarella and its listed substitutes, plus the two outside the list
    "466375", "466151", "473986", "468526", "475908", "463383", "470836",
    # scene 4, standing order lines and their listed substitutes
    "463968", "469648", "471863", "471376", "476523",
    # claim examples and the gluten backup
    "465346", "462031", "476955", "468465", "470863",
    # an id Valio does not know, to record the error flag
    "999999999",
]
MAX_IDS = 200


def demo_ids(cat: Catalog) -> list[str]:
    ids = list(SCENE_IDS)
    # every lactose related milk the matcher could pick as a candidate
    for p in cat.search(text="milk", category_prefix="104", limit=1000):
        if {"FREE_FROM_LACTOSE", "LOW_LACTOSE"} & p.claims or "lactose" in p.name_en.lower():
            ids.append(p.id)
    for p in cat.search(text="mozzarella", claims={"FREE_FROM_LACTOSE"}, limit=200):
        ids.append(p.id)
    for i in list(ids):
        p = cat.get(i)
        if p:
            ids.extend(p.substitutes)
    return list(dict.fromkeys(ids))


def main() -> int:
    s = load_settings()
    if s.valio_mode != "record":
        print("set VALIO_MODE=record")
        return 2
    ids = demo_ids(Catalog(s.catalog_db))
    client = ValioClient(s.valio_base_url, s.valio_api_key, "record", s.valio_cache, customer=s.valio_customer,
                         chunk=40)
    budget = CallBudget(MAX_IDS)
    quotes = client.price(ids, MONDAY, budget)
    avail = client.availability(ids, MONDAY, budget)
    print(f"recorded {len(quotes)} prices and {len(avail)} availabilities for {len(ids)} ids "
          f"in {budget.calls} calls, ids per call {budget.per_call}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
