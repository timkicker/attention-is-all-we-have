"""The database matches contract/schema.sql and the loaded seed answers the demo probes."""

import json
import re
from pathlib import Path

from contract.engine import DIM, FIXTURES, b64_to_vec, claim_hash

SCHEMA = Path(__file__).resolve().parents[2] / "contract" / "schema.sql"
TABLES = re.findall(r"^CREATE TABLE (\w+)", SCHEMA.read_text(), re.M)
VERSIONED = {"section_text", "claim", "claim_life_fi", "term_hit", "ref_stat"}


def test_schema_lists_all_tables():
    assert len(TABLES) == 20
    assert {"claim", "article_vec", "verdict", "check_run", "stat"} <= set(TABLES)


def test_every_table_exists(cur):
    cur.execute("SHOW TABLES")
    assert set(TABLES) <= {r[0] for r in cur.fetchall()}


def test_columns_match_schema(cur):
    text = SCHEMA.read_text()
    for table in TABLES:
        body = text.split(f"CREATE TABLE {table} (", 1)[1].split(") WITH", 1)[0].split(");", 1)[0]
        body = re.sub(r"--[^\n]*", "", body)
        expected = {
            m.group(1)
            for m in re.finditer(r"(?:^|,)\s*(\w+)\s+(?!KEY|INDEX)[A-Z]", body)
            if m.group(1) not in {"PRIMARY", "KEY", "VECTOR", "PERIOD", "UNIQUE"}
        }
        cur.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name=%s",
            (table,),
        )
        assert expected == {r[0] for r in cur.fetchall()}, table


def test_vector_indexes(cur):
    cur.execute(
        "SELECT table_name, index_name FROM information_schema.statistics"
        " WHERE table_schema=DATABASE() AND index_type='VECTOR'"
    )
    assert {r[0] for r in cur.fetchall()} == {"claim", "article_vec"}
    for table in ("claim", "article_vec"):
        cur.execute(f"SHOW CREATE TABLE {table}")
        assert "`DISTANCE`='cosine'" in cur.fetchone()[1]


def test_system_versioned_tables(cur):
    cur.execute(
        "SELECT table_name FROM information_schema.tables"
        " WHERE table_schema=DATABASE() AND table_type='SYSTEM VERSIONED'"
    )
    assert {r[0] for r in cur.fetchall()} == VERSIONED


def test_session_settings(cur):
    cur.execute("SELECT @@session.time_zone, @@session.mhnsw_ef_search")
    assert cur.fetchone() == ("+00:00", 1000)


def test_seed_loaded(cur):
    cur.execute("SELECT COUNT(*), COUNT(DISTINCT lang) FROM claim FOR SYSTEM_TIME ALL")
    n, langs = cur.fetchone()
    assert n >= 400 and langs >= 6
    cur.execute("SELECT VEC_ToText(emb) FROM claim LIMIT 1")
    assert len(json.loads(cur.fetchone()[0])) == DIM


def test_claim_hash_matches_rows(cur):
    cur.execute("SELECT text, h FROM claim FOR SYSTEM_TIME ALL LIMIT 50")
    for text, h in cur.fetchall():
        assert claim_hash(text) == h


def test_mainila_probe(cur):
    sql = (
        "SELECT text FROM claim FOR SYSTEM_TIME AS OF TIMESTAMP %s"
        " WHERE lang='en' AND topic_id='winterwar' AND text LIKE '%%Mainila%%'"
    )
    cur.execute(sql, ("2008-06-01 00:00:00",))
    then = " ".join(r[0] for r in cur.fetchall())
    cur.execute(sql, ("2012-06-01 00:00:00",))
    later = " ".join(r[0] for r in cur.fetchall())
    assert "staged" in then and "reported" not in then
    assert "reported" in later and "staged the Shelling" not in later


def test_as_of_with_vector_search(cur):
    """The statement behind Compare: AS OF and VEC_DISTANCE_COSINE together."""
    cur.execute("SELECT emb FROM claim WHERE lang='fi' AND h='8519fbaf22d33984'")
    (emb,) = cur.fetchone()
    cur.execute(
        "SELECT lang, h, VEC_DISTANCE_COSINE(emb, %s) AS d"
        " FROM claim FOR SYSTEM_TIME AS OF TIMESTAMP '2024-01-01 00:00:00' WHERE lang='de' ORDER BY d LIMIT 3",
        (emb,),
    )
    rows = cur.fetchall()
    assert rows and rows[0][1] == "176471723f110570"


def test_fixture_vectors_copy_seed_rows(cur):
    for h, item in json.loads((FIXTURES / "embed.json").read_text()).items():
        assert claim_hash(item["text"]) == h
        lang, src = item["copy_of"].split(":")
        cur.execute("SELECT VEC_ToText(emb) FROM claim FOR SYSTEM_TIME ALL WHERE lang=%s AND h=%s LIMIT 1", (lang, src))
        seed = json.loads(cur.fetchone()[0])
        assert max(abs(a - b) for a, b in zip(seed, b64_to_vec(item["emb"]), strict=True)) < 1e-6


def test_no_user_names(cur):
    for table in TABLES:
        cur.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name=%s",
            (table,),
        )
        assert not {r[0] for r in cur.fetchall()} & {"user", "user_name", "username", "editor"}
