"""Read-only access to data/catalog.db. No process but index_catalog.py loads the big JSON."""

import re
import sqlite3
import threading
from pathlib import Path

from .model import Product


class Catalog:
    def __init__(self, path: Path):
        if not Path(path).is_file():
            raise FileNotFoundError(f"{path} missing, run make data index")
        self.path = Path(path)
        # one read-only connection per thread: the web app shares this Catalog across its request threads, and
        # one sqlite3 connection used by two threads at once returns empty or mixed rows, so a product that
        # exists came back missing and stayed missing in the cache
        self._local = threading.local()
        self._cache: dict[str, Product | None] = {}

    @property
    def con(self) -> sqlite3.Connection:
        con = getattr(self._local, "con", None)
        if con is None:
            con = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)
            con.row_factory = sqlite3.Row
            self._local.con = con
        return con

    def _all(self, sql: str, *args) -> list[sqlite3.Row]:
        return self.con.execute(sql, args).fetchall()

    def get(self, product_id: str) -> Product | None:
        if product_id in self._cache:
            return self._cache[product_id]
        rows = self._all("select * from product where id = ?", product_id)
        p = self._build(rows[0]) if rows else None
        self._cache[product_id] = p
        return p

    def _build(self, r: sqlite3.Row) -> Product:
        pid = r["id"]
        allergens = self._all("select code, level from allergen where product_id = ?", pid)

        def level(lv: str) -> frozenset[str]:
            return frozenset(a["code"] for a in allergens if a["level"] == lv)

        rel = self._all("select value from reliability where product_id = ?", pid)
        co2 = self._all("select kg_co2e_per_kg from carbon where product_id = ?", pid)
        planted = self._all("select text from planted where product_id = ? and language = 'en'", pid)
        return Product(
            id=pid, name_en=r["name_en"] or "", name_fi=r["name_fi"], category=r["category"] or "",
            vendor=r["vendor"] or "", sales_unit=r["sales_unit"], base_unit=r["base_unit"],
            units={u["unit_id"]: u["size_in_base"]
                   for u in self._all("select unit_id, size_in_base from unit where product_id = ?", pid)},
            base_volume_l=r["base_volume_l"], base_weight_kg=r["base_weight_kg"],
            claims=frozenset(c["claim"] for c in self._all("select claim from claim where product_id = ?", pid)),
            contains=level("CONTAINS"), may_contain=level("MAY_CONTAIN"), free_from=level("FREE_FROM"),
            has_allergen_data=bool(r["has_allergen_data"]), lacs_g=r["lacs_g"],
            key_ingredients_en=r["key_ingredients_en"], marketing_en=r["marketing_en"],
            planted_en=planted[0]["text"] if planted else None,
            substitutes=tuple(s["substitute_id"] for s in self._all(
                "select substitute_id from substitution where product_id = ? order by position", pid)),
            reliability=rel[0]["value"] if rel else None,
            carbon_kg_per_kg=co2[0]["kg_co2e_per_kg"] if co2 else None,
            labels=frozenset(lb["code"] for lb in self._all("select code from label where product_id = ?", pid)),
            temperature=r["temperature"], deleted=bool(r["deleted"]),
        )

    def search(self, text: str | None = None, category_prefix: str | None = None,
               claims: set[str] | None = None, limit: int = 50) -> list[Product]:
        sql = "select p.id from product p where p.deleted = 0"
        args: list = []
        if text:
            words = re.findall(r"\w+", text)
            if words:
                sql += " and p.id in (select id from product_fts where product_fts match ?)"
                args.append(" ".join(f'"{w}"*' for w in words))
        if category_prefix:
            sql += " and p.category like ?"
            args.append(category_prefix + "%")
        for c in sorted(claims or ()):
            sql += " and exists (select 1 from claim c where c.product_id = p.id and c.claim = ?)"
            args.append(c)
        sql += " order by p.id limit ?"
        args.append(limit)
        return [self.get(r["id"]) for r in self._all(sql, *args)]

    def group_sizes(self) -> dict[str, int]:
        """Products per top level category (the first three digits), counted once."""
        if getattr(self, "_group_sizes", None) is None:
            rows = self._all("select substr(category, 1, 3) g, count(*) n from product where deleted = 0 group by g")
            self._group_sizes = {r["g"]: r["n"] for r in rows}
        return self._group_sizes

    def substitutes_of(self, product_id: str) -> list[Product]:
        p = self.get(product_id)
        if p is None:
            return []
        return [s for s in (self.get(i) for i in p.substitutes) if s is not None]
