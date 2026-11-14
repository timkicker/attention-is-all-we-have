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


def test_every_account_has_its_own_kitchen_key_and_issuer(c, syn_ctx):
    from fastapi.testclient import TestClient as TC

    from validio.agent.holder import Holder
    from validio.demo import seed

    assert c.post("/api/account/signup", json=SIGNUP).status_code == 201
    a = account(c)
    with TC(app) as other:
        assert other.post("/api/account/signup", json={**SIGNUP, "email": "b@example.com"}).status_code == 201
        b = account(other)
    keys = {k.kitchen_pub.thumbprint() for k in (a, b, syn_ctx)}
    assert len(keys) == 3  # no account shares the template's or another account's key
    assert seed.issuer(a.db_path) == f"kitchen:{a.account['id']}" != seed.issuer(b.db_path)
    for k in (a, b):
        assert k.audit.verify().ok  # the copied ledger's head is signed again by the new key
    # kitchen A's pass, presented with A's agent key, is refused by kitchen B
    seed.sign_again(a.db_path, a.keys_dir, {}, why="test")
    holder = Holder(seed.issuance(a.db_path), seed.load_or_create_key(a.keys_dir / "agent-es256.json"),
                    lambda: c.get(f"/agent/v1/k/{b.account['id']}/nonce").json())
    from validio.policy.mandate import MandateError

    with pytest.raises(MandateError):
        b.verify(holder.presentation())


def test_wrong_codes_lock_for_15_minutes_not_for_good(c, syn_ctx, monkeypatch):
    from validio.api import ui

    clock = [1000.0]
    monkeypatch.setattr(ui.time, "monotonic", lambda: clock[0])
    for _ in range(5):
        assert c.put("/api/rules", json=RULES, headers={"X-Approve-Code": "000000"}).status_code == 403
    r = c.put("/api/rules", json=RULES, headers={"X-Approve-Code": "246810"})
    assert r.status_code == 429 and r.headers["retry-after"] == "900"
    clock[0] += 15 * 60 + 1
    assert c.put("/api/rules", json=RULES, headers={"X-Approve-Code": "246810"}).status_code == 200


def test_the_client_behind_a_trusted_proxy_is_the_forwarded_one(c, monkeypatch):
    from types import SimpleNamespace

    from validio.api.limits import client_ip

    r = SimpleNamespace(headers={"x-forwarded-for": "198.51.100.4, 10.0.0.1"}, client=SimpleNamespace(host="10.0.0.1"))
    assert client_ip(r) == "10.0.0.1"  # never trusted without the switch
    monkeypatch.setenv("VALIDIO_TRUST_PROXY", "1")
    assert client_ip(r) == "198.51.100.4"


def test_changing_the_login_needs_the_password_and_is_rate_limited(c):
    assert c.post("/api/account/signup", json=SIGNUP).status_code == 201
    for _ in range(5):
        assert c.put("/api/settings/login", json={"currentPassword": "wrong one", "password": "x" * 9}).status_code == 403
    assert c.put("/api/settings/login", json={"currentPassword": SIGNUP["password"]}).status_code == 429


RULES = {"aloneUpToCents": 100000, "approvalUpToCents": 200000, "substitutes": "listed", "maxExtraPct": 0,
         "perWeekCents": None}


def test_new_kitchens_are_rate_limited_per_client(c):
    from validio.api.limits import NEW_KITCHENS

    for i in range(NEW_KITCHENS.limit):
        with TestClient(app) as fresh:  # a new browser each time, so each asks for a new copy
            assert fresh.post("/api/account/demo").status_code == 200, i
    with TestClient(app) as fresh:
        assert fresh.post("/api/account/demo").status_code == 429
        assert fresh.post("/api/account/signup", json=SIGNUP).status_code == 429


def test_demo_copies_stay_under_the_cap(c, monkeypatch):
    from validio.api import accounts

    monkeypatch.setattr(accounts, "MAX_DEMO_COPIES", 3)
    for _ in range(5):
        with TestClient(app) as fresh:
            assert fresh.post("/api/account/demo").status_code == 200
    with accounts.get_accounts()._db() as con:
        assert con.execute("select count(*) from account where is_demo = 1").fetchone()[0] == 3


def test_an_account_dropped_from_the_cache_keeps_working_for_its_request(c, monkeypatch):
    from validio.api import accounts

    monkeypatch.setattr(accounts, "MAX_OPEN", 1)
    assert c.post("/api/account/signup", json=SIGNUP).status_code == 201
    held = account(c)  # a request still working on it
    with TestClient(app) as other:
        assert other.post("/api/account/demo").status_code == 200  # pushes `held` out of the cache
    held.audit.append(at=held.stamp(), actor="validio", kind="decision", sentence="still open", facts=[],
                      mandate_id=None, disclosed={}, rule_ids=[], order_id=None)
    assert held.audit.verify().ok
    assert account(c).audit.list()[-1].sentence == "still open"  # a fresh runtime sees the same file


def test_a_new_password_ends_the_other_sessions(c):
    assert c.post("/api/account/signup", json=SIGNUP).status_code == 201
    with TestClient(app) as phone:
        assert phone.post("/api/account/login", json={"email": SIGNUP["email"],
                                                      "password": SIGNUP["password"]}).status_code == 200
        assert c.put("/api/settings/login", json={"currentPassword": SIGNUP["password"],
                                                  "password": "a new long one"}).status_code == 200
        assert phone.get("/api/account").status_code == 401
    assert c.get("/api/account").status_code == 200  # the session that changed it stays


def test_login_runs_scrypt_for_an_unknown_email_too(c, monkeypatch):
    from validio.api import accounts

    calls = []
    real = accounts.secret_ok
    monkeypatch.setattr(accounts, "secret_ok", lambda s, h: calls.append(h) or real(s, h))
    assert c.post("/api/account/login", json={"email": "nobody@example.com", "password": "x" * 9}).status_code == 401
    assert calls == [accounts._DUMMY_HASH]


def test_cookies_are_secure_on_a_public_deploy_behind_a_proxy(monkeypatch):
    from types import SimpleNamespace

    from validio.api.limits import secure_cookies

    plain = SimpleNamespace(url=SimpleNamespace(scheme="http"), headers={"x-forwarded-proto": "https"})
    assert not secure_cookies(plain)
    monkeypatch.setenv("VALIDIO_TRUST_PROXY", "1")
    assert secure_cookies(plain)
    monkeypatch.setenv("VALIDIO_TRUST_PROXY", "")
    monkeypatch.setenv("VALIDIO_PUBLIC", "1")
    assert secure_cookies(plain)


def test_an_own_account_has_no_borrowed_steady_order(c):
    assert c.post("/api/account/signup", json=SIGNUP).status_code == 201
    assert c.get("/api/steady").json() == []
    assert c.get("/api/steady/S-1").status_code == 404
    assert c.post("/api/steady/S-1/renew", headers={"X-Approve-Code": SIGNUP["approvalCode"]}).status_code == 404


def test_last_weeks_renewal_does_not_block_this_week(syn_ctx):
    from datetime import timedelta
    from types import SimpleNamespace

    from validio.api import steady

    so, _h = steady._steady()
    live = syn_ctx.rt.live()
    target = steady.next_renewals(so.weekday, live.service.clock(), 1)[0]
    steady._save(live.path, so.id, {"view": {}, "delivery": target.isoformat()})
    assert steady._this_week(live, so) is not None
    later = SimpleNamespace(path=live.path, service=SimpleNamespace(clock=lambda: live.service.clock() + timedelta(days=7)))
    assert steady._this_week(later, so) is None  # a week on: renew again
