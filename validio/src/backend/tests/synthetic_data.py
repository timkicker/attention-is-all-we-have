"""A tiny SYNTHETIC data set in the shape of Valio's files, so CI runs the decision path without Valio's data.

Every product here is invented: ids 900001 to 900009, names starting with "SYNTHETIC", made-up prices and stock.
None of it comes from Valio. `build(dir)` writes the three raw files and recorded price and availability answers,
then runs the real indexer, so the catalog goes through the same code as the real one.
"""

import csv
import json
import subprocess
import sys
from pathlib import Path

DAY = "2026-11-16"
CLOSING = "2026-11-15T12:00:00+0200"
SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"


def _product(pid, name, category, sales_unit, units, *, litres=None, kg=None, claims=(), allergens=(),
             lacs=None, substitutes=(), ingredients=None):
    conv = {"synkkaPackagingType": "BASE_UNIT_OR_EACH"}
    if litres:
        conv["volume"] = {"unit": "LTR", "value": litres}
    if kg:
        conv["netWeight"] = {"unit": "KGM", "value": kg}
    classifications = [
        {"name": "nutritionalClaim", "values": [{"id": c} for c in claims]},
        {"name": "allergen", "values": [{"id": c, "unit": lv} for c, lv in allergens]},
    ]
    if lacs is not None:
        classifications.append({"name": "nutritionFact", "values": [{"id": "LACS", "value": lacs}]})
    return {
        "id": pid, "category": category, "vendorName": "SYNTHETIC vendor", "salesUnit": sales_unit,
        "baseUnit": "ST", "temperatureCondition": 6, "deleted": False,
        "units": [{"unitId": u, "sizeInBaseUnits": n} for u, n in units.items()],
        "substitutions": [{"substituteProduct": s} for s in substitutes],
        "synkkaData": {
            "names": [{"language": "en", "value": f"SYNTHETIC {name}"}],
            "classifications": classifications,
            "unitConversions": [conv],
            "keyIngredients": [{"language": "en", "value": ingredients}] if ingredients else [],
            "marketingTexts": [],
        },
    }


MILK = {"claims": ("FREE_FROM_LACTOSE",), "allergens": (("AM", "CONTAINS"),), "lacs": 0.0, "litres": 1.0}
CHEESE = {"claims": ("FREE_FROM_LACTOSE",), "allergens": (("AM", "CONTAINS"),), "lacs": 0.0}

PRODUCTS = [
    _product("900001", "lactose free milk drink 1 l", "10400", "ST", {"ST": 1, "KI": 12}, **MILK),
    _product("900002", "lactose free organic milk drink 1 l", "10400", "ST", {"ST": 1, "KI": 12}, **MILK),
    _product("900003", "milk drink 1 l", "10400", "ST", {"ST": 1}, litres=1.0, claims=("FREE_FROM_LACTOSE",),
             allergens=(("AM", "CONTAINS"), ("ML", "CONTAINS")), lacs=4.8),
    _product("900004", "lactose free milk drink 1 l box", "10400", "KI", {"ST": 1, "KI": 12}, **MILK),
    _product("900005", "lactose free cheese 1 kg", "10600", "ST", {"ST": 1}, kg=1.0,
             substitutes=("900006", "900007"), **CHEESE),
    _product("900006", "lactose free cheese 2 kg", "10600", "ST", {"ST": 1}, kg=2.0, **CHEESE),
    _product("900007", "cheese 1 kg", "10600", "ST", {"ST": 1}, kg=1.0, claims=("FREE_FROM_LACTOSE",),
             allergens=(("AM", "CONTAINS"), ("ML", "CONTAINS")), lacs=3.0),
    _product("900008", "lactose free milk drink 1 l discontinued", "10400", "ST", {"ST": 1}, **MILK),
    _product("900009", "lactose free milk drink 1 l from the supplier", "10400", "ST", {"ST": 1}, **MILK),
]

# id: (price EUR per sales unit, logistic model, amount, unit Valio answers in). None = no delivery line.
LIVE = {
    "900001": (1.00, "Stock", 5000.0, "ST"),
    "900002": (2.50, "Stock", 9999999999.0, "ST"),  # Valio's placeholder number, invented product
    "900003": (0.80, "Stock", 5000.0, "ST"),
    "900004": (12.00, "Stock", 36.0, "ST"),  # 36 ST are 3 boxes of 12
    "900005": (10.00, "Stock", 10.0, "ST"),
    "900006": (20.40, "Stock", 100.0, "ST"),
    "900007": (9.00, "Stock", 100.0, "ST"),
    "900008": (1.10, None, None, None),
    "900009": (1.05, "Terminal", 999999.0, "ST"),
}
RELIABILITY = {"900001": 0.98, "900002": 0.95, "900004": 0.97, "900005": 0.99, "900006": 0.99}
CARBON = {"900001": 1.2, "900002": 1.1, "900005": 9.0, "900006": 9.0}


def _price(pid: str) -> dict:
    eur = LIVE[pid][0]
    return {"productId": pid, "error": False, "netPriceFound": True,
            "catalogPrice": {"value": eur, "validTo": "2026-12-31T23:59:59+0200"},
            "listPrice": {"value": eur}, "tax": {"taxRate": 14.0}}


def _availability(pid: str) -> dict:
    _, model, amount, unit = LIVE[pid]
    if model is None:
        return {"productId": pid, "logisticModel": "Stock", "closingTime": CLOSING, "salesBlock": False,
                "scheduleLines": []}
    return {"productId": pid, "logisticModel": model, "closingTime": CLOSING, "salesBlock": False,
            "scheduleLines": [{"availableAmount": amount, "availableDate": DAY, "salesUnit": unit,
                               "salesBlock": False}]}


def build(root: Path) -> tuple[Path, Path]:
    """Write the synthetic set under `root`. Returns (catalog.db, cache dir for replay)."""
    raw, cache = root / "raw", root / "cache"
    raw.mkdir(parents=True, exist_ok=True)
    (raw / "valio_aimo_junction26_product_data.json").write_text(json.dumps(PRODUCTS))
    for name, col, rows in (("delivery_reliability", "deliveryReliability", RELIABILITY),
                            ("carbon_footprint", "AVG kg CO2-eq/kg", CARBON)):
        with (raw / f"valio_aimo_junction26_{name}.csv").open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["productId", col])
            w.writerows(rows.items())
    for endpoint, row in (("price", _price), ("availability", _availability)):
        d = cache / endpoint / DAY
        d.mkdir(parents=True, exist_ok=True)
        resp = {"timeNow": "2026-11-14T10:00:00+0200", "products": [row(pid) for pid in LIVE]}
        (d / "synthetic.json").write_text(json.dumps({"endpoint": endpoint, "requestedDate": DAY,
                                                      "ids": sorted(LIVE), "response": resp}))
    db = root / "catalog.db"
    subprocess.run([sys.executable, str(SCRIPTS / "index_catalog.py"), "--raw", str(raw), "--out", str(db),
                    "--planted", str(root / "no-planted.json")], check=True, capture_output=True)
    return db, cache
