import json
import os

import pytest

from api.tests.conftest import schema_errors

MAX = "2106-02-07 06:28:15.999999"
LANGS = ("fi", "sv", "de", "en", "ru", "et", "uk")


@pytest.fixture
def ref_stats():
    """Two snapshots per edition, written as history rows like A14 loads them, removed afterwards."""
    from contract.db import connect

    conn = connect()
    c = conn.cursor()
    c.execute("SET system_versioning_insert_history = ON")
    for i, lang in enumerate(LANGS):
        old = {"FI": 2, "EN": 1} if lang == "fi" else {"EN": 3}
        new = {"FI": 78, "EN": 3, "SE": 1} if lang == "fi" else {"EN": 40 + i, "FI": i}
        c.execute(
            "INSERT INTO ref_stat (topic_id, lang, rev_id, refs, isbn, domains, row_start, row_end) VALUES "
            "('winterwar', %s, %s, %s, %s, %s, '2010-01-01', '2020-01-01'),"
            "('winterwar', %s, %s, %s, %s, %s, '2020-01-01', %s)",
            (
                lang,
                1000 + i,
                10 + i,
                json.dumps(old),
                json.dumps({"books.google.com": 2}),
                lang,
                2000 + i,
                100 + i,
                json.dumps(new),
                json.dumps({"yle.fi": 4, "books.google.com": 9}),
                MAX,
            ),
        )
    c.execute("SET system_versioning_insert_history = OFF")
    yield
    c.execute("DELETE FROM ref_stat")
    c.execute("DELETE HISTORY FROM ref_stat")
    conn.close()


def test_seven_editions_today(client, ref_stats):
    body = client.get("/api/sources", params={"topic": "winterwar"}).json()
    assert not schema_errors("/api/sources", body)
    assert [e["lang"] for e in body["editions"]] == list(LANGS)
    fi = body["editions"][0]
    assert fi["rev_id"] == 2000 and fi["refs"] == 100
    assert list(fi["isbn"]) == ["FI", "EN", "SE"]  # most cited first
    assert fi["domains"] == {"books.google.com": 9, "yle.fi": 4}
    assert any("FOR SYSTEM_TIME AS OF" in s["text"] for s in body["sql"])


def test_as_of_cuts_every_edition_at_the_same_instant(client, ref_stats):
    body = client.get("/api/sources", params={"topic": "winterwar", "as_of": "2015-06-01"}).json()
    assert {e["rev_id"] for e in body["editions"]} == {1000 + i for i in range(7)}
    assert client.get("/api/sources", params={"topic": "winterwar", "as_of": "2005-01-01"}).json()["editions"] == []


def test_empty_until_a14(client):
    body = client.get("/api/sources", params={"topic": "winterwar"}).json()
    assert body["editions"] == [] and not schema_errors("/api/sources", body)


def test_unknown_topic_is_404_and_topic_is_required(client):
    assert client.get("/api/sources", params={"topic": "nope"}).status_code == 404
    assert client.get("/api/sources").status_code == 422


@pytest.mark.skipif(os.environ.get("PARALLAX_SEED") not in ("v3", "v4"), reason="needs seed v3 or later (ref_stat)")
def test_seven_editions_on_a_full_seed(client):
    # PLAN B8 done check:
    # PARALLAX_SEED=v4 PARALLAX_SEED_DB=parallax uv run pytest api/tests/test_sources.py -k full_seed
    body = client.get("/api/sources", params={"topic": "winterwar"}).json()
    assert len(body["editions"]) == 7
