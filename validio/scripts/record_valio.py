"""One read-only pass against Valio's test API: price and availability for every product id the five demo
scenes and the kitchen phrases touch, for each delivery day, stored under data/cache/valio/<endpoint>/<day>/
for replay. 40 ids per HTTP call, a pause between calls. An id already recorded for a day is never asked again.

    record_valio.py                          the weekdays of the demo's next week (Mon 16 to Fri 20 Nov 2026)
    record_valio.py --days 2026-11-17,...    only these days
    record_valio.py 470863 ...               these ids as well
"""

import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "backend"))
from validio.catalog.store import Catalog
from validio.config import load_settings
from validio.demo.seed import NOW, WEEK_START
from validio.valio.budget import CallBudget
from validio.valio.client import ValioClient

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
CHUNK = 40
# what a kitchen types live: the candidates the parser finds for these, with and without the lactose-free
# rule, plus their listed substitutes
KITCHEN_PHRASES = [
    "200 litres of cream", "100 litres of whipping cream", "50 litres of cooking cream", "50 kg of sour cream",
    "50 kg of butter", "40 kg of cheese", "20 kg of emmental", "20 kg of edam", "20 kg of gouda",
    "30 kg of cheddar", "40 kg of feta", "20 kg of halloumi", "30 kg of cream cheese", "20 kg of cottage cheese",
    "50 kg of quark", "100 kg of yoghurt", "100 kg of yogurt", "30 cartons of eggs", "30 cartons of pancakes",
    "20 kg of parmesan", "40 kg of margarine", "30 kg of pudding", "20 kg of creme fraiche",
    "50 bags of mozzarella", "200 litres of oat drink", "100 litres of ice cream", "500 litres of milk",
]
PAUSE_S = 1.0  # between calls, the test API is shared by every team


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


def delivery_days() -> list[date]:
    """Monday to Friday of the week after the demo clock (seed.NOW, Saturday 14 November 2026)."""
    monday = WEEK_START.date() + timedelta(days=7)
    return [monday + timedelta(days=i) for i in range(5)]


def kitchen_ids(cat: Catalog) -> list[str]:
    from validio.matching.need import parse_need, screen

    ids = []
    for text in KITCHEN_PHRASES:
        for diet in (set(), {"FREE_FROM_LACTOSE"}):
            n = parse_need(f"{text} by Monday", NOW.date(), cat)
            n.kitchen_claims = diet - n.required_claims
            n.required_claims |= diet
            for p in screen(n, cat)[0]:
                ids += [p.id, *p.substitutes]
    return list(dict.fromkeys(ids))


def recorded(cache: Path, endpoint: str, day: date | None = None) -> set[str]:
    """The ids with a recorded answer on that day, or on any day."""
    files = (cache / endpoint).glob(f"{day.isoformat() if day else '*'}/*.json")
    return {x["productId"] for f in files for x in json.loads(f.read_text())["response"]["products"]}


def parse_days(argv: list[str]) -> list[date]:
    if "--days" not in argv:
        return delivery_days()
    return [date.fromisoformat(d) for d in argv[argv.index("--days") + 1].split(",")]


def main() -> int:
    s = load_settings()
    if s.valio_mode != "record":
        print("set VALIO_MODE=record")
        return 2
    days = parse_days(sys.argv[1:])
    cat = Catalog(s.catalog_db)
    extra = [a for a in sys.argv[1:] if a.isdigit()]
    # every day gets what any day has, so a day recorded later answers the same questions as Monday
    wanted = list(dict.fromkeys(demo_ids(cat) + kitchen_ids(cat) + extra
                                + sorted(recorded(s.valio_cache, "price") | recorded(s.valio_cache, "availability"))))
    client = ValioClient(s.valio_base_url, s.valio_api_key, "record", s.valio_cache, customer=s.valio_customer,
                         chunk=CHUNK)
    total = 0
    for day in days:
        have = recorded(s.valio_cache, "price", day) & recorded(s.valio_cache, "availability", day)
        ids = [i for i in wanted if i not in have]  # never twice: replay refuses a clash
        budget = CallBudget(len(ids) * 2 + 1)
        for i in range(0, len(ids), CHUNK):
            part = ids[i:i + CHUNK]
            client.price(part, day, budget)
            time.sleep(PAUSE_S)
            client.availability(part, day, budget)
            time.sleep(PAUSE_S)
        total += budget.calls
        print(f"{day:%a} {day}: recorded {len(ids)} new ids in {budget.calls} calls, {len(have)} were recorded before")
    print(f"{total} calls in all")
    return 0


if __name__ == "__main__":
    sys.exit(main())
