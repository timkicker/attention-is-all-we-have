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


@pytest.fixture(autouse=True)
def _fake_model(monkeypatch):
    """The agent's model reads validio/.env, so a developer's Gemini key there would make tests call Gemini.
    Every test runs the fake twin unless it changes LLM_MODE itself; GeminiLLM.from_env() is not affected."""
    monkeypatch.setenv("LLM_MODE", "fake")


@pytest.fixture(autouse=True)
def _no_live_fallback(monkeypatch):
    """VALIO_LIVE_FALLBACK=1 in validio/.env would let replay ask Valio's test API with the key there: tests never
    leave the machine. A test of the fallback builds its client with live_fallback=True and mocks the HTTP."""
    monkeypatch.setenv("VALIO_LIVE_FALLBACK", "0")


@pytest.fixture(autouse=True)
def _fresh_rate_limits():
    """Rate limits are per process: every test starts with empty windows, so one test's calls never 429 the next."""
    from validio.api import accounts, limits

    for v in vars(limits).values():
        if isinstance(v, limits.RateLimiter):
            v.clear()
    accounts._tries.clear()  # the login's and the password change's misses
    yield


@pytest.fixture(scope="session")
def catalog():
    from validio.catalog.store import Catalog

    db = load_settings().catalog_db
    if not db.is_file():
        pytest.skip(f"needs_data: {db} missing, run make data index")
    return Catalog(db)


# the agent API and the web app API over one runtime in a temporary store (test_api, test_mcp)
CODE = "246810"


class Spy:
    """Counts every question to Valio."""

    def __init__(self, inner):
        self.inner, self.calls = inner, 0

    @property
    def mode(self):
        return getattr(self.inner, "mode", None)

    def recorded_days(self):
        return self.inner.recorded_days()

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
    monkeypatch.setenv("VALIDIO_DEMO", "1")
    for k in ("VALIDIO_PUBLIC", "VALIDIO_PUBLIC_READ", "VALIDIO_KITCHEN_TOKEN", "VALIDIO_MCP_HOSTS"):
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




@pytest.fixture(scope="session")
def synthetic(tmp_path_factory):
    """The SYNTHETIC catalog and recorded answers (tests/synthetic_data.py): runs without Valio's data, in CI."""
    from synthetic_data import build

    return build(tmp_path_factory.mktemp("synthetic"))


@pytest.fixture
def syn_ctx(tmp_path, synthetic, monkeypatch):
    """The local kitchen and the account routes over the synthetic set, the way `ctx` sets them up over Valio's."""
    from validio.api.state import Ctx, set_ctx
    from validio.api.steady import Runtime
    from validio.catalog.store import Catalog
    from validio.demo import seed
    from validio.valio.client import ValioClient

    db, cache = synthetic
    monkeypatch.setenv("VALIDIO_APPROVE_CODE", CODE)
    monkeypatch.setenv("VALIDIO_DEMO", "1")
    for k in ("VALIDIO_PUBLIC", "VALIDIO_PUBLIC_READ", "VALIDIO_KITCHEN_TOKEN", "VALIDIO_MCP_HOSTS",
              "VALIDIO_TRUST_PROXY"):
        monkeypatch.setenv(k, "")
    monkeypatch.setenv("VALIDIO_DB", str(tmp_path / "validio.db"))
    monkeypatch.setenv("VALIDIO_KEYS", str(tmp_path / "keys"))
    monkeypatch.setenv("VALIDIO_ACCOUNTS", str(tmp_path / "accounts"))
    monkeypatch.setenv("VALIDIO_TEMPLATE", str(tmp_path / "no-template"))
    monkeypatch.setenv("VALIDIO_VALIO_CACHE", str(cache))
    seed.reset()
    rt = Runtime()
    rt._catalog = Catalog(db)
    rt._valio = Spy(ValioClient("https://junction26.valioaimo.fi", "", "replay", cache))
    c = Ctx(rt)
    set_ctx(c)
    yield c
    set_ctx(None)
