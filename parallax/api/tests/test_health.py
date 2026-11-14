from api.tests.conftest import schema_errors


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert not schema_errors("/api/health", body)
    assert body["db"] == "ok"
    assert body["engine"] == "fake"
    assert body["model_id"] == "fake-judge"
    assert body["counts"]["claim"] == 413
    assert body["counts"]["verdict"] == 12


def test_health_reports_the_loaded_seed(client, monkeypatch):
    # conftest loads contract/fixtures/seed-mini.sql, so the database says mini whatever .env says
    monkeypatch.setenv("SEED", "v1")
    assert client.get("/api/health").json()["seed"] == "mini"


def test_every_response_carries_timed_sql(client):
    body = client.get("/api/health").json()
    st = body["sql"][0]
    assert "FROM claim FOR SYSTEM_TIME ALL" in st["text"]
    assert st["ms"] >= 0 and st["rows"] == 1 and st["index"] == "none"


def test_topics(client):
    body = client.get("/api/topics").json()
    assert not schema_errors("/api/topics", body)
    (ww,) = [t for t in body["topics"] if t["topic_id"] == "winterwar"]
    assert [e["lang"] for e in ww["editions"]] == ["fi", "sv", "de", "en", "ru", "et"]
    fi = ww["editions"][0]
    assert fi["title"] == "Talvisota" and fi["first_ts"] == "2005-12-31T19:28:39Z"
    assert body["sql"][0]["text"].lstrip().startswith("SELECT")


def test_stats(client):
    body = client.get("/api/stats").json()
    assert not schema_errors("/api/stats", body)
    assert isinstance(body["stats"], dict)


def test_sql_panel_keeps_last_run(client):
    client.get("/api/topics")
    body = client.get("/api/sql/topics").json()
    assert not schema_errors("/api/sql/{panel_id}", body)
    assert body["panel_id"] == "topics"
    assert body["statements"] and "FROM topic" in body["statements"][0]["text"]


def test_unknown_panel_is_error_shape(client):
    r = client.get("/api/sql/nope")
    assert r.status_code == 404
    assert not schema_errors("/api/sql/{panel_id}", r.json(), status="404")
    assert r.json()["error"]["code"] == "panel_not_found"


def test_vector_statement_reports_index(client):
    from api import sqllog

    with sqllog.capture() as log:
        (row,) = sqllog.run("SELECT emb FROM claim LIMIT 1")
        sqllog.run("SELECT h, VEC_DISTANCE_COSINE(emb, %s) AS d FROM claim ORDER BY d LIMIT 3", (row["emb"],))
        sqllog.run("SELECT h FROM claim IGNORE INDEX(emb) ORDER BY VEC_DISTANCE_COSINE(emb, %s) LIMIT 3", (row["emb"],))
    assert [s["index"] for s in log] == ["none", "emb", "none"]
    assert log[1]["rows"] == 3


def test_statement_log_names_its_parameters(client):
    from api import sqllog

    with sqllog.capture() as log:
        sqllog.run(
            "SELECT h FROM claim WHERE topic_id = %(topic)s AND h IN %(hs)s LIMIT 1",
            {"topic": "winterwar", "hs": ("a", "b", "c")},
        )
        sqllog.run("SELECT h FROM claim LIMIT 1")
    assert log[0]["params"] == {"topic": "winterwar", "hs": {"count": 3}}
    assert log[1]["params"] == {}
