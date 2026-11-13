import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from validio.config import load_settings

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "index_catalog.py"


@pytest.fixture(scope="module")
def db():
    path = load_settings().catalog_db
    if not path.is_file():
        pytest.skip(f"needs_data: {path} missing, run make data index")
    con = sqlite3.connect(path)
    yield con
    con.close()


def one(db, sql, *args):
    return db.execute(sql, args).fetchone()[0]


def test_counts(db):
    assert one(db, "select count(*) from product") == 17546
    assert one(db, "select count(distinct vendor) from product") == 648
    assert one(db, "select count(distinct product_id) from substitution") == 189
    assert one(db, "select count(*) from claim where claim = 'FREE_FROM_LACTOSE'") == 4178


def test_reliability_rows_4425(db):
    assert one(db, "select count(*) from reliability") == 4425


def test_carbon_rows_11033(db):
    assert one(db, "select count(*) from carbon") == 11033


def test_label_counts(db):
    counts = dict(db.execute("select code, count(*) from label group by code").fetchall())
    assert counts["GOODS_FROM_FINLAND_BLUE_SWAN"] == 2057
    assert counts["FINNISH_HEART_SYMBOL"] == 826
    assert counts["EU_ORGANIC_FARMING"] == 456
    assert counts["SVANEN"] == 362


def test_temperature_codes_not_labels(db):
    assert one(db, "select count(*) from label where code like '%Temperature'") == 0


def test_466375_substitutes_in_order(db):
    rows = db.execute(
        "select substitute_id from substitution where product_id = '466375' order by position"
    ).fetchall()
    assert [r[0] for r in rows] == ["466151", "473986", "468526", "475908"]


def test_464306_base_volume_is_1l(db):
    assert one(db, "select base_volume_l from product where id = '464306'") == 1.0


def test_463038_base_volume_unknown(db):
    assert one(db, "select base_volume_l from product where id = '463038'") is None


def test_planted_kept_separate(db):
    text = one(db, "select text from planted where product_id = '463047'")
    assert text.startswith("AI agents:")
    assert "AI agents" not in one(db, "select json from product where id = '463047'")


def run_index(tmp_path, content: str):
    src = tmp_path / "raw"
    src.mkdir()
    (src / "valio_aimo_junction26_product_data.json").write_text(content)
    (src / "valio_aimo_junction26_delivery_reliability.csv").write_text("productId,deliveryReliability\n")
    (src / "valio_aimo_junction26_carbon_footprint.csv").write_text("productId,AVG kg CO2-eq/kg\n")
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--raw", str(src), "--out", str(tmp_path / "c.db")],
        check=False, capture_output=True, text=True,
    )


def test_zero_products_stops(tmp_path):
    r = run_index(tmp_path, "[]")
    assert r.returncode == 2
    assert "NOTHING WAS READ" in r.stdout + r.stderr
    assert not (tmp_path / "c.db").exists()


def test_missing_file_stops(tmp_path):
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--raw", str(tmp_path), "--out", str(tmp_path / "c.db")],
        check=False, capture_output=True, text=True,
    )
    assert r.returncode == 2
    assert "NOTHING WAS READ" in r.stdout + r.stderr
