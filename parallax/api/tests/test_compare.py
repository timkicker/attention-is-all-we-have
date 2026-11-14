import pytest

from api import sqllog
from api.tests.conftest import schema_errors

MAINILA = "fi:1256:8519fbaf22d33984"
FI_DEAD = "fi:1256:6fcbf86eca6b8af2"
MAINILA_SECTION = "Suomen ja Neuvostoliiton neuvottelut aluemuutoksista"
LANGS = ["fi", "sv", "de", "en", "ru", "et"]


@pytest.fixture(scope="module")
def today(client):
    r = client.get("/api/compare", params={"topic": "winterwar", "anchor": "fi", "limit": 200})
    assert r.status_code == 200
    return r.json()


def row(body, row_id):
    (r,) = [x for x in body["rows"] if x["row_id"] == row_id]
    return r


def test_matches_contract(today):
    assert not schema_errors("/api/compare", today)
    assert today["langs"] == LANGS
    assert set(today["editions"]) == set(LANGS)
    assert today["total_rows"] == len(today["rows"]) == 49


def test_mainila_row_has_cells_in_all_six_editions(today):
    cells = row(today, MAINILA)["cells"]
    assert list(cells) == LANGS
    assert cells["fi"]["status"] == "anchor"
    assert all(cells[x]["status"] in ("matched", "candidate") and cells[x]["text"] for x in LANGS[1:])
    assert cells["en"]["verdict"]["label"] == "partial"
    assert {"kind": "term", "this": "lavasti", "other": "reported"} in cells["en"]["marks"]
    assert cells["de"]["oldid_url"] == "https://de.wikipedia.org/w/index.php?oldid=271092734"


def test_finnish_dead_marks_differing_numbers_only(today):
    cells = row(today, FI_DEAD)["cells"]
    # seed-mini has no Swedish casualty sentence, so the fi/sv number mark of PLAN B3 needs seed v2;
    # here en (25,904) carries it and de writes the same number as 26.662, which is no mark.
    assert cells["en"]["marks"] == [{"kind": "number", "this": "26 662", "other": "25,904"}]
    assert cells["en"]["verdict"]["label"] == "contradicts" and cells["en"]["status"] == "matched"
    assert cells["de"]["status"] == "matched" and cells["de"]["marks"] == []


def test_glosses_are_attached(today):
    assert row(today, MAINILA)["cells"]["fi"]["gloss"].startswith("The Soviet Union staged")


def test_one_statement_with_as_of_and_vector_distance(today):
    texts = [s["text"] for s in today["sql"]]
    (stmt,) = [t for t in texts if "VEC_DISTANCE_COSINE" in t]
    assert "FOR SYSTEM_TIME AS OF" in stmt and "IGNORE INDEX (emb)" in stmt
    assert all(s["index"] == "none" for s in today["sql"])


def test_as_of_cuts_every_edition(client):
    body = client.get("/api/compare", params={"topic": "winterwar", "as_of": "2008-06-01", "limit": 200}).json()
    assert not schema_errors("/api/compare", body)
    assert body["as_of"] == "2008-06-01T00:00:00Z"
    assert body["editions"]["en"]["rev_id"] == 33225464
    assert "et" not in body["editions"]  # et has no parsed revision before 2009
    for r in body["rows"]:
        assert r["cells"]["et"]["status"] == "not_found"
        assert r["cells"]["fi"]["born"] <= "2008-06-01T00:00:00Z"


def test_paging_and_section(client):
    p1 = client.get("/api/compare", params={"topic": "winterwar", "limit": 5}).json()
    p2 = client.get("/api/compare", params={"topic": "winterwar", "limit": 5, "offset": 5}).json()
    assert len(p1["rows"]) == len(p2["rows"]) == 5 and p1["total_rows"] == 49
    assert not {r["row_id"] for r in p1["rows"]} & {r["row_id"] for r in p2["rows"]}
    sec = client.get("/api/compare", params={"topic": "winterwar", "section": "Osapuolten tappiot", "limit": 50}).json()
    assert sec["rows"] and {r["section"] for r in sec["rows"]} == {"Osapuolten tappiot"}


def test_langs_subset(client):
    body = client.get("/api/compare", params={"topic": "winterwar", "langs": "en,de", "limit": 3}).json()
    assert body["langs"] == ["fi", "de", "en"]
    assert all(list(r["cells"]) == ["fi", "de", "en"] for r in body["rows"])


def test_unknown_topic_is_404(client):
    r = client.get("/api/compare", params={"topic": "nope"})
    assert r.status_code == 404
    assert not schema_errors("/api/compare", r.json(), status="404")
    assert r.json()["error"]["code"] == "topic_not_found"


def test_align_cache_is_read_for_its_date(client):
    sqllog.run("DELETE FROM align")
    sqllog.run(
        "INSERT INTO align VALUES ('2026-11-14', 'fi', 1256, '8519fbaf22d33984', 'en', 1, 33924, 'a3b291dafd10d41b',"
        " 0.2, 'exact')"
    )
    try:
        body = client.get(
            "/api/compare", params={"topic": "winterwar", "as_of": "2026-11-14", "section": MAINILA_SECTION}
        ).json()
        assert any("FROM align" in s["text"] for s in body["sql"])
        assert not any("VEC_DISTANCE_COSINE" in s["text"] for s in body["sql"])
        cells = row(body, MAINILA)["cells"]
        assert cells["en"]["h"] == "a3b291dafd10d41b" and cells["en"]["dist"] == 0.2
        assert cells["de"]["status"] == "not_found"
    finally:
        sqllog.run("DELETE FROM align")
