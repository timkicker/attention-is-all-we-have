import os

import pytest

from api.tests.conftest import schema_errors

RU_STAGED = "ac5853856a89a0eb"  # "... инсценированный советской стороной ..." (staged by the Soviet side)
EN_STAGED = "7aee25bc3466a2fc"


def by_h(body, h):
    return next(r for r in body["rows"] if r["h"] == h)


def test_matches_contract(client):
    body = client.get("/api/dropped", params={"topic": "winterwar"}).json()
    assert not schema_errors("/api/dropped", body)
    assert body["total"] == len(body["rows"]) or body["total"] > len(body["rows"])


def test_ru_staged_clause_is_dropped_while_de_still_states_it(client):
    body = client.get("/api/dropped", params={"topic": "winterwar"}).json()
    ru = by_h(body, RU_STAGED)
    assert ru["lang"] == "ru" and ru["died_rev"] == 89813748 and ru["days"] >= 365
    alive = {a["lang"]: a for a in ru["alive_in"]}
    assert {"fi", "de", "sv"} <= set(alive)
    assert alive["de"]["h"] == "176471723f110570"
    assert alive["de"]["verdict"]["label"] == "same"
    assert alive["de"]["oldid_url"].startswith("https://de.wikipedia.org/w/index.php?oldid=")
    assert "ru" not in alive
    # the last revision that still had the sentence: the snapshot before the one that dropped it
    assert ru["last_url"] == f"https://ru.wikipedia.org/w/index.php?oldid={ru['last_rev']}"
    assert ru["last_rev"] != ru["died_rev"]


def test_en_staged_is_dropped_with_matches_through_fi(client):
    en = by_h(client.get("/api/dropped", params={"topic": "winterwar", "lang": "en"}).json(), EN_STAGED)
    assert en["died"] == "2009-12-31T20:28:48Z"
    assert [a["lang"] for a in en["alive_in"]] == ["fi", "sv", "de", "ru", "et"]
    assert en["gloss"] is None or en["gloss"]


def test_rows_sorted_by_days_alive_and_paged(client):
    body = client.get("/api/dropped", params={"topic": "winterwar"}).json()
    days = [r["days"] for r in body["rows"]]
    assert days == sorted(days, reverse=True)
    one = client.get("/api/dropped", params={"topic": "winterwar", "limit": 1, "offset": 1}).json()
    assert one["total"] == body["total"] and one["rows"][0]["h"] == body["rows"][1]["h"]


def test_min_days_filters(client):
    body = client.get("/api/dropped", params={"topic": "winterwar", "min_days": 5000}).json()
    assert body["rows"] == [] and body["total"] == 0


def test_bad_reason_is_422(client):
    r = client.get("/api/dropped", params={"reason": "biased"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "bad_reason"


@pytest.fixture
def fi_lives():
    """Three Finnish lives written with SET timestamp so they become history rows, cleaned up afterwards."""
    from contract.db import connect

    conn = connect()
    c = conn.cursor()

    c.execute(
        "INSERT INTO revision (lang, rev_id, page_id, parent_id, ts, comment) "
        "VALUES ('fi', 9000002, 77, 9000001, '2014-03-01', 'lähteetön')"
    )
    c.execute("SET system_versioning_insert_history = ON")
    c.execute(
        "INSERT INTO claim_life_fi (page_id, h, text, born_rev, died_rev, died_comment, reason, row_start, row_end) "
        "VALUES "
        "(77, 'aaaaaaaaaaaaaaaa', 'Kylässä asui vuonna 1900 noin 400 ihmistä.', 9000000, 9000002, 'lähteetön',"
        " 'unsourced', '2010-01-01', '2014-03-01'),"
        "(77, 'bbbbbbbbbbbbbbbb', 'Kirkko rakennettiin vuonna 1820.', 9000000, NULL, NULL, 'none', '2010-01-01',"
        " '2106-02-07 06:28:15.999999'),"
        "(77, 'cccccccccccccccc', 'Asema avattiin lyhyeksi aikaa.', 9000000, 9000003, NULL, 'none', '2010-01-01',"
        " '2010-02-01')"
    )
    c.execute("SET system_versioning_insert_history = OFF")
    conn.commit()
    yield
    c.execute("DELETE FROM claim_life_fi")
    c.execute("DELETE HISTORY FROM claim_life_fi")
    c.execute("DELETE FROM revision WHERE rev_id = 9000002")
    conn.commit()
    conn.close()


def test_fi_scale_mode(client, fi_lives):
    body = client.get("/api/dropped", params={"lang": "fi"}).json()
    assert not schema_errors("/api/dropped", body)
    assert body["total"] == 1
    (row,) = body["rows"]
    assert row["h"] == "aaaaaaaaaaaaaaaa" and row["reason"] == "unsourced" and row["died_comment"] == "lähteetön"
    assert row["last_url"] == "https://fi.wikipedia.org/w/index.php?oldid=9000001"
    assert body["scale"]["fi_lives"] >= 3 and body["scale"]["fi_dead"] >= 2 and body["scale"]["fi_dead_1y"] >= 1
    assert client.get("/api/dropped", params={"reason": "error"}).json()["total"] == 0
    assert client.get("/api/dropped", params={"reason": "unsourced"}).json()["total"] == 1


def test_fi_mode_refuses_other_editions(client):
    r = client.get("/api/dropped", params={"lang": "sv"})
    assert r.status_code == 422


@pytest.mark.skipif(
    os.environ.get("PARALLAX_SEED") not in ("v2", "v3", "v4"), reason="needs seed v2 or later (exact bisect of 2014)"
)
def test_ru_staged_clause_on_a_full_seed(client):
    # PLAN B5 done check:
    # PARALLAX_SEED=v4 PARALLAX_SEED_DB=parallax uv run pytest api/tests/test_dropped.py -k full_seed
    body = client.get("/api/dropped", params={"topic": "winterwar", "lang": "ru", "limit": 200}).json()
    ru = [r for r in body["rows"] if "инсценированный советской стороной" in r["text"]]
    assert any(r["died_rev"] == 64106894 and "de" in {a["lang"] for a in r["alive_in"]} for r in ru)


def test_cut_span_finds_the_one_cut():
    from api.routes.dropped import cut_span

    text = "Stalin expected the Red Army to reach Helsinki within twelve days."
    end = cut_span(text, "Stalin expected the Red Army to reach Helsinki.")
    assert text[end["start"] : end["end"]] == "within twelve days." and end["end"] == len(text)
    mid = cut_span("The Soviet Union staged the shots.", "The Soviet Union the shots.")
    assert mid == {"start": 17, "end": 23}
    assert cut_span(text, "Stalin hoped the Red Army would reach Helsinki.") is None  # reworded, not cut
    assert cut_span(text, text) is None
    assert cut_span("A — B c d", "A B c d") is None  # only a dash went


def test_rows_carry_the_removed_part(client):
    body = client.get("/api/dropped", params={"topic": "winterwar", "limit": 200}).json()
    for r in body["rows"]:
        assert r["removed"] is None or 0 <= r["removed"]["start"] < r["removed"]["end"] <= len(r["text"])
        assert r["removed"] is None or "words_en" in r["removed"]


def test_cut_words_trims_the_trailing_comma():
    from api.routes.dropped import cut_words

    assert cut_words("Stalin hoped, staged, the end", {"start": 13, "end": 21}) == "staged"


def test_scale_prefers_stored_stat_keys(monkeypatch):
    from api import sqllog
    from api.routes import dropped as d

    stored = {"fi_lives": 1118463, "fi_dead": 532372, "fi_dead_1y": 292344, "fi_revisions": 862076}
    counted = {"fi_lives": 9, "fi_dead": 8, "fi_dead_1y": 7, "fi_revisions": 2143}

    def fake(name, params=None):
        if name == "dropped_stat":
            return [{"k": k, "v": str(v)} for k, v in stored.items()]
        assert name == "dropped_scale", "all keys stored: nothing is counted"
        return [counted]

    monkeypatch.setattr(sqllog, "run_file", fake)
    assert d.scale() == stored
    del stored["fi_revisions"]  # a missing key falls back to the count, the others stay stored
    assert d.scale() == {"fi_lives": 1118463, "fi_dead": 532372, "fi_dead_1y": 292344, "fi_revisions": 2143}
