"""POST/GET /api/ingest and a whole ingest job on recorded texts (offline: Wikimedia and embedding are faked)."""

import json
from pathlib import Path

import pytest

from api.routes import ingest as ingest_route
from pipeline import job, wapi

TEXTS = json.loads((Path(__file__).parent / "recorded" / "ingest-texts.json").read_text())
QID = "Q90000001"
ENTITY = {
    QID: {
        "labels": {"en": {"value": "Test Line"}},
        "descriptions": {"en": {"value": "defensive line"}},
        "sitelinks": {
            "fiwiki": {"title": "Testilinja"},
            "svwiki": {"title": "Testlinjen"},
            "enwiki": {"title": "Test Line"},
        },
    },
    "Q90000002": {"labels": {"en": {"value": "No Finnish"}}, "sitelinks": {"enwiki": {"title": "No Finnish"}}},
    "Q90000004": {
        "labels": {"en": {"value": "Sample Line"}},
        "sitelinks": {"fiwiki": {"title": "Testilinja"}, "svwiki": {"title": "Testlinjen"}},
    },
}  # fmt: skip
PAGE_IDS = {"fi": 990001, "sv": 990002, "en": 990003}


def fake_fetch(lang, title, since, progress):
    progress(30)
    texts = TEXTS[lang]
    snaps = [
        {"rev_id": PAGE_IDS[lang] * 10 + i, "ts": f"{2015 + 5 * i}-03-01T10:00:00Z", "sha1": f"{lang}{i}",
         "comment": "edit", "text": t}
        for i, t in enumerate(texts)
    ]  # fmt: skip
    meta = [{k: s[k] for k in ("rev_id", "ts", "sha1", "comment")} | {"bytes": len(s["text"])} for s in snaps]
    return {"lang": lang, "title": title, "page_id": PAGE_IDS[lang], "length": len(texts[-1]), "meta": meta,
            "snaps": snaps}  # fmt: skip


@pytest.fixture
def offline(client, monkeypatch):
    if ingest_route.WORKER:  # run the job in the test thread instead
        ingest_route.WORKER.close()
        ingest_route.WORKER = None
    monkeypatch.setenv("EMBED_BACKEND", "fake")
    monkeypatch.setattr(job, "fetch_edition", fake_fetch)
    monkeypatch.setattr(job, "current_length", lambda lang, title: len(TEXTS[lang][-1]))

    def get(url, params=None, **kw):
        assert params.get("action") == "wbgetentities"
        return {"entities": {q: ENTITY[q] for q in params["ids"].split("|") if q in ENTITY}}

    monkeypatch.setattr(wapi, "get", get)
    return client


def test_unknown_qid_404(client):
    r = client.get("/api/ingest/Q1")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


def test_loaded_topic_is_done(client):
    d = client.get("/api/ingest/Q134949").json()
    assert d["state"] == "done" and d["topic_id"] == "winterwar"
    assert [e["lang"] for e in d["editions"]] == ["fi", "sv", "de", "en", "ru", "et", "uk"]


def test_loaded_topic_by_topic_id(client):
    # the Differences and Removed tabs of /t/winterwar watch the ingest under the route id
    d = client.get("/api/ingest/winterwar").json()
    assert d["state"] == "done" and d["qid"] == "Q134949"


def test_no_finnish_422(offline):
    r = offline.post("/api/ingest", json={"qid": "Q90000002"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "no_finnish"


def test_bad_qid_422(client):
    assert client.post("/api/ingest", json={"qid": "Winter War"}).status_code == 422


def test_rate_limited_429(client, monkeypatch):
    def get(url, params=None, **kw):
        raise wapi.RateLimited("429", 120)

    monkeypatch.setattr(wapi, "get", get)
    r = client.post("/api/ingest", json={"qid": "Q90000003"})
    assert r.status_code == 429 and r.headers["Retry-After"] == "120"
    assert r.json()["error"] == {"code": "rate_limited", "message": r.json()["error"]["message"], "retry_after_s": 120}


def test_ingest_end_to_end(offline):
    r = offline.post("/api/ingest", json={"qid": QID})
    assert r.status_code == 202
    d = r.json()
    assert d["job_id"] == QID and d["topic_id"] == "q90000001" and d["state"] == "queued"
    states = {e["lang"]: (e["state"], e["error"]) for e in d["editions"]}
    assert states["fi"] == ("waiting", None) and states["ru"] == ("failed", "no_article")
    again = offline.post("/api/ingest", json={"qid": QID}).json()  # idempotent
    assert again["state"] == "queued" and again["since"] is None
    narrowed = offline.post("/api/ingest", json={"qid": QID, "since": "2021-01-01"}).json()  # "Faster" link
    assert narrowed["state"] == "queued" and narrowed["since"] == "2021-01-01"
    offline.post("/api/ingest", json={"qid": QID, "since": "2010-01-01"})  # an earlier date never widens it
    assert offline.get(f"/api/ingest/{QID}").json()["since"] == "2021-01-01"

    assert job.run_job(QID) == "done"
    d = offline.get(f"/api/ingest/{QID}").json()
    assert d["state"] == "done" and d["eta_s"] is None
    done = [e["lang"] for e in d["editions"] if e["state"] == "done"]
    assert done == ["fi", "sv", "en"] and all(e["pct"] == 100 for e in d["editions"] if e["state"] == "done")

    topics = offline.get("/api/topics").json()["topics"]
    t = next(t for t in topics if t["topic_id"] == "q90000001")
    assert t["wikidata_id"] == QID and t["label_en"] == "Test Line"
    assert [e["lang"] for e in t["editions"]] == ["fi", "sv", "en"]

    cmp = offline.get("/api/compare", params={"topic": "q90000001"}).json()
    assert cmp["total_rows"] > 0 and cmp["langs"] == ["fi", "sv", "en"]
    cells = [r["cells"]["sv"] for r in cmp["rows"]]
    assert any(c["verdict"] and c["verdict"]["model"] == "fake-judge-similarity" for c in cells)

    # history: the Summa date changed in fi between the two snapshots
    old = offline.get("/api/compare", params={"topic": "q90000001", "as_of": "2016-01-01"}).json()
    assert any("13. helmikuuta" in r["cells"]["fi"]["text"] for r in old["rows"])
    assert not any("13. helmikuuta" in r["cells"]["fi"]["text"] for r in cmp["rows"])

    assert job.run_job(QID) == "done"  # rerun is a no-op
    hit = offline.post("/api/ingest", json={"qid": QID}).json()
    assert hit["state"] == "done"


def test_ingest_takes_over_a_page_of_the_finnish_sample(offline, monkeypatch):
    """Jatkosota, Mannerheim and others are in the Finnish M sample as lives without a topic: loading the article
    must still give it a Finnish edition, with its history (an M life ending at the same instant keeps its row)."""
    from contract.db import connect
    from pipeline.load import versioned

    def fetch(lang, title, since, progress):
        f = fake_fetch(lang, title, since, progress)
        shift = lambda r: r | {"rev_id": r["rev_id"] + 50}  # noqa: E731
        return f | {"page_id": f["page_id"] + 5, "meta": [shift(r) for r in f["meta"]],
                    "snaps": [shift(r) for r in f["snaps"]]}  # fmt: skip

    monkeypatch.setattr(job, "fetch_edition", fetch)
    fi = fetch("fi", "Testilinja", None, lambda pct: None)
    w = job.lives_of(fi)
    sample = [lv | {"lang": "fi", "page_id": fi["page_id"], "topic_id": None, "emb": b"\0\0\x80?" * 1024}
              for lv in w.lives]  # fmt: skip
    assert any(lv["row_end"] for lv in sample)  # the sample also holds a life that ended
    conn = connect()
    with conn.cursor() as cur:
        cur.execute("INSERT INTO page (lang, page_id, title, source, history) VALUES ('fi', %s, 'Testilinja', 'M', "
                    "'every')", (fi["page_id"],))  # fmt: skip
        cur.execute("SET system_versioning_insert_history=1")
        versioned(cur, "claim", ["lang", "page_id", "h", "topic_id", "section", "text", "born_rev", "emb"], sample)
    conn.commit()
    conn.close()

    assert offline.post("/api/ingest", json={"qid": "Q90000004"}).status_code == 202
    assert job.run_job("Q90000004") == "done"
    cmp = offline.get("/api/compare", params={"topic": "q90000004"}).json()
    assert cmp["langs"] == ["fi", "sv"] and cmp["total_rows"] > 0
    old = offline.get("/api/compare", params={"topic": "q90000004", "as_of": "2016-01-01"}).json()
    assert any("13. helmikuuta" in r["cells"]["fi"]["text"] for r in old["rows"])
    h = cmp["rows"][0]["row_id"].split(":")[2]
    lives = offline.get(f"/api/claim/fi/{fi['page_id']}/{h}/timeline").json()["lives"]
    assert [x["lang"] for x in lives].count("fi") == 1
