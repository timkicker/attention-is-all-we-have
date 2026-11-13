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


def test_settings_repr_hides_the_api_key(monkeypatch):
    from validio.config import load_settings

    monkeypatch.setenv("VALIO_API_KEY", "k-should-never-print-123")
    s = load_settings(None)
    assert s.valio_api_key == "k-should-never-print-123"
    assert "k-should-never-print-123" not in repr(s)


def test_eur_formats_negative_amounts():
    from validio.audit.sentences import eur as eur_ledger
    from validio.matching.reasons import eur as eur_reasons

    for eur in (eur_ledger, eur_reasons):
        assert eur(-150) == "-1.50 €"
        assert eur(-5) == "-0.05 €"
        assert eur(0) == "0.00 €"
        assert eur(101000) == "1,010.00 €"
