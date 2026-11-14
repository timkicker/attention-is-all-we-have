"""Kitchen accounts over the synthetic set: runs without Valio's data (tests/conftest.py, syn_ctx)."""

import pytest
from fastapi.testclient import TestClient

from validio.api.app import app

SIGNUP = {"name": "Synthetic kitchen", "email": "chef@example.com", "password": "correct horse",
          "customerNumber": "12345", "approvalCode": "135790"}


@pytest.fixture
def c(syn_ctx):
    with TestClient(app) as client:
        yield client


def account(c):
    from validio.api.accounts import get_accounts

    return get_accounts().ctx(c.get("/api/account").json()["id"])


def test_signup_works_on_the_synthetic_set(c):
    r = c.post("/api/account/signup", json=SIGNUP)
    assert r.status_code == 201, r.text
    assert c.get("/api/account").json()["email"] == "chef@example.com"


def test_nonce_route_is_rate_limited_per_client(c):
    from validio.api.limits import NONCES

    for _ in range(NONCES.limit):
        assert c.get("/agent/v1/nonce").status_code == 200
    r = c.get("/agent/v1/nonce")
    assert r.status_code == 429 and r.headers["retry-after"] == "60"
    with TestClient(app, client=("203.0.113.9", 50000)) as other:
        assert other.get("/agent/v1/nonce").status_code == 200  # another client is not held up


def test_own_account_decides_on_the_wall_clock_with_its_own_pass_window(c):
    from datetime import datetime

    from validio.demo import seed
    from validio.demo.seed import issuance, issued_claims

    assert c.post("/api/account/signup", json=SIGNUP).status_code == 201
    k = account(c)
    assert abs((k.now() - datetime.now(k.now().tzinfo)).total_seconds()) < 5  # not the demo clock
    claims = issued_claims(issuance(k.db_path))
    now = datetime.now().timestamp()
    assert claims["deliverBy"] is None
    assert claims["nbf"] <= now < claims["exp"] and claims["exp"] - now > 29 * 24 * 3600
    assert seed.window_ok(k.db_path, k.now())
    # many ledger entries no longer push the decision time towards the pass's end
    for _ in range(50):
        k.audit.append(at=k.stamp(), actor="validio", kind="decision", sentence="x", facts=[], mandate_id=None,
                       disclosed={}, rule_ids=[], order_id=None)
    assert abs((k.now() - datetime.now(k.now().tzinfo)).total_seconds()) < 5


def test_own_account_pass_is_renewed_before_it_runs_out(c, monkeypatch):
    from datetime import timedelta

    from validio.api.accounts import get_accounts
    from validio.demo import seed
    from validio.demo.seed import issuance, issued_claims

    assert c.post("/api/account/signup", json=SIGNUP).status_code == 201
    k = account(c)
    v = seed.pass_version(k.db_path, seed.SPEND_PASS_ID)
    # 25 days later: fewer than seven days are left
    later = k.now() + timedelta(days=25)
    monkeypatch.setattr(type(k), "now", lambda self: later)
    k._window_at = -1e9
    get_accounts().ctx(k.account["id"])
    assert seed.pass_version(k.db_path, seed.SPEND_PASS_ID) == v + 1
    assert issued_claims(issuance(k.db_path))["exp"] > (later + timedelta(days=29)).timestamp()
    assert "for 30 more days" in k.audit.list()[-1].sentence


def test_demo_copy_keeps_the_demo_clock(c):
    from validio.demo.seed import NOW

    assert c.post("/api/account/demo").status_code == 200
    k = account(c)
    assert k.now() >= NOW and (k.now() - NOW).days < 3
