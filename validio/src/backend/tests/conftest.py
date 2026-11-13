import os

import pytest

from validio.config import load_settings


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """REQUIRE_DATA=1 (set by `make test`): a test that skips for missing Valio data fails instead, so a local
    run never looks green without the data. CI leaves it unset and runs the synthetic set (test_synthetic.py)."""
    outcome = yield
    rep = outcome.get_result()
    if os.environ.get("REQUIRE_DATA") == "1" and rep.skipped and "needs_data" in str(rep.longrepr):
        rep.outcome = "failed"


@pytest.fixture(scope="session")
def catalog():
    from validio.catalog.store import Catalog

    db = load_settings().catalog_db
    if not db.is_file():
        pytest.skip(f"needs_data: {db} missing, run make data index")
    return Catalog(db)


# the agent API and the web app API over one runtime in a temporary store (test_api, test_mcp)
CODE, TOKEN = "246810", "demo-test-token"


class Spy:
    """Counts every question to Valio."""

    def __init__(self, inner):
        self.inner, self.calls = inner, 0

    def price(self, *a, **kw):
        self.calls += 1
        return self.inner.price(*a, **kw)

    def availability(self, *a, **kw):
        self.calls += 1
        return self.inner.availability(*a, **kw)


@pytest.fixture
def ctx(tmp_path, catalog, monkeypatch):
    from validio.api.steady import Runtime
    from validio.config import load_settings
    from validio.demo import seed
    from validio.valio.client import ValioClient

    s = load_settings()
    if not any(s.valio_cache.glob("price/*/*.json")):
        pytest.skip("needs_data: no recorded Valio answers, run make record")
    monkeypatch.setenv("VALIDIO_APPROVE_CODE", CODE)
    monkeypatch.setenv("VALIDIO_DEMO_TOKEN", TOKEN)
    monkeypatch.setenv("VALIDIO_DEMO", "1")
    for k in ("VALIDIO_PUBLIC", "VALIDIO_KITCHEN_TOKEN", "VALIDIO_MCP_HOSTS"):
        monkeypatch.setenv(k, "")
    monkeypatch.setenv("VALIDIO_DB", str(tmp_path / "validio.db"))
    monkeypatch.setenv("VALIDIO_KEYS", str(tmp_path / "keys"))
    seed.reset()
    rt = Runtime()
    rt._valio = Spy(ValioClient(s.valio_base_url, "", "replay", s.valio_cache))
    from validio.api.state import Ctx, set_ctx

    c = Ctx(rt)
    set_ctx(c)
    yield c
    set_ctx(None)


