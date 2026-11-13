from fastapi.testclient import TestClient


def test_app_imports():
    from validio.api.app import app

    assert app.title == "Validio"


def test_config_reads_env(monkeypatch):
    from validio.config import load_settings

    monkeypatch.setenv("VALIO_MODE", "live")
    monkeypatch.setenv("VALIO_MAX_IDS_PER_REQUEST", "7")
    s = load_settings(env_file=None)
    assert s.valio_mode == "live"
    assert s.valio_max_ids == 7


def test_config_defaults_to_replay(monkeypatch):
    from validio.config import load_settings

    monkeypatch.delenv("VALIO_MODE", raising=False)
    s = load_settings(env_file=None)
    assert s.valio_mode == "replay"
    assert s.valio_max_ids == 40


def test_health():
    from validio.api.app import app

    r = TestClient(app).get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
