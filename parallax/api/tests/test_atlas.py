import os

import pytest

from api.tests.conftest import schema_errors

ROWS = [
    ("Q134949", "Talvisota", "Vinterkriget", "Winter War", "all", 0.12, 0.14, 0.11, "winterwar"),
    ("Q1", "Maailmankaikkeus", "Universum", "Universe", "all", 0.30, 0.05, 0.20, None),
    ("Q20", "Norja", "Norge", None, "fi+sv", 0.40, None, None, None),
    ("Q33", "Suomi", None, "Finland", "fi+en", None, 0.25, None, None),
    ("Q99", "Pikkukylä", None, None, "fi", None, None, None, None),
]


@pytest.fixture
def atlas_rows():
    from contract.db import connect

    conn = connect()
    c = conn.cursor()
    c.executemany("INSERT INTO atlas_topic VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)", ROWS)
    conn.commit()
    yield
    c.execute("DELETE FROM atlas_topic")
    conn.commit()
    conn.close()


def test_counts_per_coverage_and_contract(client, atlas_rows):
    body = client.get("/api/atlas").json()
    assert not schema_errors("/api/atlas", body)
    assert body["counts"] == {"all": 2, "fi+sv": 1, "fi+en": 1, "fi": 1}
    assert [t["wikidata_id"] for t in body["topics"]] == ["Q1", "Q20", "Q33", "Q99", "Q134949"]
    ww = body["topics"][-1]
    assert ww["topic_id"] == "winterwar" and ww["titles"]["sv"] == "Vinterkriget" and ww["dist"]["fi_en"] == 0.14


def test_filter_sort_and_page(client, atlas_rows):
    body = client.get("/api/atlas", params={"coverage": "all"}).json()
    assert {t["wikidata_id"] for t in body["topics"]} == {"Q1", "Q134949"}
    assert body["counts"]["fi"] == 1  # counts stay for every coverage
    by_fi_sv = client.get("/api/atlas", params={"sort": "fi_sv"}).json()["topics"]
    assert [t["wikidata_id"] for t in by_fi_sv] == ["Q20", "Q1", "Q134949", "Q33", "Q99"]  # NULL last
    page = client.get("/api/atlas", params={"limit": 2, "offset": 2}).json()["topics"]
    assert [t["wikidata_id"] for t in page] == ["Q33", "Q99"]
    assert client.get("/api/atlas", params={"sort": "dist_fi_sv; DROP TABLE x"}).status_code == 422
    assert client.get("/api/atlas", params={"coverage": "de"}).status_code == 422


def test_empty_until_a_seed_has_the_atlas(client):
    body = client.get("/api/atlas").json()
    assert body["counts"] == {"all": 0, "fi+sv": 0, "fi+en": 0, "fi": 0} and body["topics"] == []


@pytest.mark.skipif(os.environ.get("PARALLAX_SEED") != "v3", reason="needs seed v3 (atlas from Track A)")
def test_counts_all_on_seed_v3(client):
    # PLAN B10 done check. After M2:
    # PARALLAX_SEED=v3 PARALLAX_SEED_DB=parallax uv run pytest api/tests/test_atlas.py -k v3
    assert client.get("/api/atlas").json()["counts"]["all"] == 2919
