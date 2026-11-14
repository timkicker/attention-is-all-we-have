import os

import pytest

from api import sqllog
from api.tests.conftest import schema_errors

FI_MAINILA = "/api/claim/fi/1256/8519fbaf22d33984/timeline"
EN_STAGED = "/api/claim/en/33924/7aee25bc3466a2fc/timeline"


def lives_of(body, lang, h=None):
    return [x for x in body["lives"] if x["lang"] == lang and (h is None or x["h"] == h)]


def test_matches_contract(client):
    body = client.get(FI_MAINILA).json()
    assert not schema_errors("/api/claim/{lang}/{page_id}/{h}/timeline", body)
    assert body["claim"]["h"] == "8519fbaf22d33984"
    assert body["claim"]["section"] == "Suomen ja Neuvostoliiton neuvottelut aluemuutoksista"
    assert body["lives"][0]["lang"] == "fi"


def test_en_mainila_life_ends_at_the_2010_snapshot_on_seed_v1(client):
    # PLAN B4: on seed v1 the "staged" life ends at the snapshot after the 2009 edit, known to the year.
    (staged,) = lives_of(client.get(EN_STAGED).json(), "en", "7aee25bc3466a2fc")
    assert staged["died"] == "2009-12-31T20:28:48Z"
    assert staged["died_rev"] == 335165674
    assert staged["time_precision"] == "snapshot"


def test_fi_claim_carries_the_en_lives_it_matched(client):
    body = client.get(FI_MAINILA).json()
    en = lives_of(body, "en")
    staged = [x for x in en if x["h"] == "7aee25bc3466a2fc"]
    assert staged and staged[0]["verdict"]["label"] == "same"
    assert staged[0]["died"] == "2009-12-31T20:28:48Z"
    current = [x for x in en if x["died"] is None]
    assert current and "reported" in current[0]["text"]
    assert [x["born"] for x in en] == sorted(x["born"] for x in en)


def test_matched_lives_follow_the_compare_pick(client):
    body = client.get(FI_MAINILA).json()
    # ru: the "staged by the Soviet side" sentence (verdict same) is part of the history
    assert any(x["h"] == "ac5853856a89a0eb" for x in lives_of(body, "ru"))
    assert {x["lang"] for x in body["lives"]} == {"fi", "sv", "de", "en", "ru", "et"}


def test_sql_is_recorded(client):
    body = client.get(FI_MAINILA).json()
    assert any("FOR SYSTEM_TIME ALL" in s["text"] for s in body["sql"])


def test_unknown_claim_is_404(client):
    r = client.get("/api/claim/fi/1256/0000000000000000/timeline")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "claim_not_found"
    assert not schema_errors("/api/claim/{lang}/{page_id}/{h}/timeline", r.json(), status="404")


@pytest.mark.skipif(
    os.environ.get("PARALLAX_SEED") not in ("v2", "v3", "v4"), reason="needs seed v2 or later (exact bisect of 2009)"
)
def test_en_mainila_life_ends_on_21_august_2009_on_a_full_seed(client):
    # PARALLAX_SEED=v4 PARALLAX_SEED_DB=parallax uv run pytest api/tests/test_timeline.py -k full_seed
    # The last "staged" sentence is found by its text: its h depends on how the seed split the text.
    (last,) = sqllog.run(
        "SELECT page_id, h FROM claim FOR SYSTEM_TIME ALL WHERE lang = 'en' AND topic_id = 'winterwar'"
        " AND text LIKE %s ORDER BY row_end DESC LIMIT 1",
        ("%the Soviets staged the shelling of Mainila%",),
    )
    body = client.get(f"/api/claim/en/{last['page_id']}/{last['h']}/timeline").json()
    (staged,) = lives_of(body, "en", last["h"])[-1:]
    assert staged["died"].startswith("2009-08-21") and staged["died_rev"] == 309285088
    assert staged["time_precision"] == "exact"


def test_judged_lives_beyond_the_nearest_are_kept(client, monkeypatch):
    # v4: fi Mainila's partial en match of 2009 to 2015 ("a border incident was reported") was not among
    # the 200 nearest en lives, so the timeline skipped it. Here the window is cut to one life per edition.
    from api.routes import timeline

    full = lives_of(client.get(FI_MAINILA).json(), "en")
    judged = {x["h"] for x in full if x["verdict"]}
    monkeypatch.setattr(timeline, "NEAREST", 1)
    cut = lives_of(client.get(FI_MAINILA).json(), "en")
    assert judged and judged <= {x["h"] for x in cut if x["verdict"]}


def test_lives_carry_gloss_field(client):
    r = client.get("/api/claim/fi/1256/8519fbaf22d33984/timeline")
    assert r.status_code == 200
    assert all("gloss" in x for x in r.json()["lives"])
