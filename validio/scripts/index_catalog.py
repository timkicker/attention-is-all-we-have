"""Build data/catalog.db from the three Valio files. The only place that loads the big JSON.

Exits 2 with NOTHING WAS READ when no product was read, so an empty index never looks fine.
"""

import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "backend"))
from validio.catalog.labels import is_label
from validio.config import DATA

PKG = Path(__file__).resolve().parents[1] / "src" / "backend" / "validio"
PRODUCTS = "valio_aimo_junction26_product_data.json"
RELIABILITY = "valio_aimo_junction26_delivery_reliability.csv"
CARBON = "valio_aimo_junction26_carbon_footprint.csv"

VOLUME_TO_L = {"LTR": 1.0, "MLT": 0.001, "CLT": 0.01}
WEIGHT_TO_KG = {"GRM": 0.001, "KGM": 1.0}


def nothing(why: str) -> int:
    print(f"NOTHING WAS READ: {why}")
    return 2


def text(items: list[dict], lang: str) -> str | None:
    vals = [i["value"] for i in items or [] if i.get("language") == lang and i.get("value")]
    return "\n".join(vals) if vals else None


def classes(s: dict) -> dict[str, list[dict]]:
    return {c["name"]: c.get("values", []) for c in s.get("classifications", [])}


def base_measures(s: dict) -> tuple[float | None, float | None]:
    vol = kg = None
    for c in s.get("unitConversions", []):
        if c.get("synkkaPackagingType") != "BASE_UNIT_OR_EACH":
            continue
        v = c.get("volume") or {}
        if v.get("unit") in VOLUME_TO_L:
            vol = v["value"] * VOLUME_TO_L[v["unit"]]
        elif v.get("unit") in WEIGHT_TO_KG:
            kg = v["value"] * WEIGHT_TO_KG[v["unit"]]
        nw = c.get("netWeight") or {}
        if kg is None and nw.get("unit") in WEIGHT_TO_KG and vol is None:
            kg = nw["value"] * WEIGHT_TO_KG[nw["unit"]]
    return vol, kg


def lacs(cl: dict) -> float | None:
    for v in cl.get("nutritionFact", []):
        if v["id"] == "LACS" and v.get("value") is not None:
            return float(v["value"])
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", type=Path, default=DATA / "raw")
    ap.add_argument("--out", type=Path, default=DATA / "catalog.db")
    ap.add_argument("--planted", type=Path, default=PKG / "demo" / "planted.json")
    args = ap.parse_args()

    src = args.raw / PRODUCTS
    if not src.is_file():
        return nothing(f"{src} does not exist")
    try:
        products = json.loads(src.read_text())
    except json.JSONDecodeError as e:
        return nothing(f"{src} is not JSON ({e})")
    if not isinstance(products, list) or not products:
        return nothing(f"{src} holds zero products")

    tmp = args.out.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(tmp)
    con.executescript((PKG / "catalog" / "schema.sql").read_text())

    for p in products:
        s = p.get("synkkaData", {})
        cl = classes(s)
        vol, kg = base_measures(s)
        allergens = [(v["id"], v.get("unit")) for v in cl.get("allergen", [])]
        allergens += [(v["id"], v.get("unit")) for v in cl.get("nonAllergen", [])]
        names = s.get("names", [])
        con.execute(
            "insert into product values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (p["id"], json.dumps(p, ensure_ascii=False), text(names, "en"), text(names, "fi"),
             p.get("category"), p.get("vendorName"), p.get("salesUnit"), p.get("baseUnit"), vol, kg,
             lacs(cl), p.get("temperatureCondition"), int(bool(p.get("deleted"))), int(bool(allergens)),
             text(s.get("marketingTexts", []), "en"), text(s.get("keyIngredients", []), "en")),
        )
        con.execute("insert into product_fts values (?,?,?,?)",
                    (p["id"], text(names, "en"), text(names, "fi"), text(names, "sv")))
        con.executemany("insert into claim values (?,?)",
                        [(p["id"], v["id"]) for v in cl.get("nutritionalClaim", [])])
        con.executemany("insert into allergen values (?,?,?)", [(p["id"], c, lv) for c, lv in allergens])
        con.executemany("insert into unit values (?,?,?)",
                        [(p["id"], u["unitId"], u.get("sizeInBaseUnits")) for u in p.get("units", [])])
        con.executemany("insert into substitution values (?,?,?)",
                        [(p["id"], x["substituteProduct"], i)
                         for i, x in enumerate(p.get("substitutions") or [])])
        con.executemany("insert into label values (?,?)",
                        [(p["id"], v["id"]) for v in cl.get("packagingMarkedLabel", []) if is_label(v["id"])])

    with (args.raw / RELIABILITY).open() as f:
        con.executemany("insert into reliability values (?,?)",
                        [(r["productId"], float(r["deliveryReliability"])) for r in csv.DictReader(f)])
    with (args.raw / CARBON).open() as f:
        con.executemany("insert into carbon values (?,?)",
                        [(r["productId"], float(r["AVG kg CO2-eq/kg"])) for r in csv.DictReader(f)])
    if args.planted.is_file():
        con.executemany("insert into planted values (?,?,?,?)",
                        [(x["productId"], x["language"], x["text"], x["note"])
                         for x in json.loads(args.planted.read_text())])
    con.commit()
    n = con.execute("select count(*) from product").fetchone()[0]
    con.close()
    if n == 0:
        tmp.unlink()
        return nothing("zero products written")
    tmp.replace(args.out)
    print(f"indexed {n} products into {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
