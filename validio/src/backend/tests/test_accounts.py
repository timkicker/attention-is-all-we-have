"""Accounts: signup, login, logout, the demo kitchen per browser, and one store per account (isolation).

Numbers from docs/ACCOUNTS-API.md and the demo script: the demo approval code 246810, scene 3's waiting
request (approve with the code), the seeded Spend Pass M-1."""

import sqlite3
import time

import pytest
from fastapi.testclient import TestClient

from validio.api import accounts as acc_mod
from validio.demo import seed

SIGNUP = {"name": "Kitchen A", "email": "a@example.org", "password": "correct horse",
          "customerNumber": "123456", "approvalCode": "135790"}


@pytest.fixture
def app_env(ctx, tmp_path, monkeypatch):
    """The local kitchen from conftest's ctx, plus accounts under tmp_path with no template (fresh seeds)."""
    monkeypatch.setenv("VALIDIO_ACCOUNTS", str(tmp_path / "accounts"))
    monkeypatch.setenv("VALIDIO_TEMPLATE", str(tmp_path / "template"))
    acc_mod._tries.clear()
    from validio.api.app import app

    return app


def client(app):
    return TestClient(app)


def connect_demo_agent(c):
    """A demo copy starts without an agent: "Connect the demo agent", then Allow."""
    assert c.post("/api/agent/demo").json()["state"] == "consent"
    assert c.post("/api/agent/allow").json()["state"] == "active"


def test_signup_sets_cookie_and_account(app_env):
    with client(app_env) as c:
        r = c.post("/api/account/signup", json=SIGNUP)
        assert r.status_code == 201
        a = r.json()
        assert a["name"] == "Kitchen A" and a["email"] == "a@example.org" and a["isDemo"] is False
        assert "demoCode" not in a
        assert a["setup"] == {"kitchen": False, "rules": False, "agent": False, "done": False}
        cookie = r.headers["set-cookie"]
        assert "validio_session=" in cookie and "HttpOnly" in cookie and "samesite=lax" in cookie.lower()
        assert c.get("/api/account").json()["id"] == a["id"]


def test_signup_rejects_bad_fields_and_duplicate(app_env):
    with client(app_env) as c:
        assert c.post("/api/account/signup", json={**SIGNUP, "approvalCode": "12345"}).status_code == 422
        assert c.post("/api/account/signup", json={**SIGNUP, "password": "short"}).status_code == 422
        assert c.post("/api/account/signup", json={**SIGNUP, "email": "nope"}).status_code == 422
        assert c.post("/api/account/signup", json=SIGNUP).status_code == 201
        r = c.post("/api/account/signup", json={**SIGNUP, "email": "A@example.org"})
        assert r.status_code == 409


def test_login_logout(app_env):
    with client(app_env) as c:
        aid = c.post("/api/account/signup", json=SIGNUP).json()["id"]
    with client(app_env) as c:
        assert c.get("/api/account").status_code == 401
        assert c.post("/api/account/login", json={"email": SIGNUP["email"], "password": "wrong one"}).status_code == 401
        r = c.post("/api/account/login", json={"email": "A@Example.org", "password": SIGNUP["password"]})
        assert r.status_code == 200 and r.json()["id"] == aid
        assert c.get("/api/account").json()["id"] == aid
        assert c.post("/api/account/logout").status_code == 204
        assert c.get("/api/account").status_code == 401


def test_login_locks_after_five_wrong(app_env):
    with client(app_env) as c:
        c.post("/api/account/signup", json=SIGNUP)
        for _ in range(5):
            assert c.post("/api/account/login", json={"email": SIGNUP["email"], "password": "x" * 8}).status_code == 401
        r = c.post("/api/account/login", json={"email": SIGNUP["email"], "password": SIGNUP["password"]})
        assert r.status_code == 429


def test_password_and_code_stored_hashed(app_env, tmp_path):
    with client(app_env) as c:
        c.post("/api/account/signup", json=SIGNUP)
    con = sqlite3.connect(tmp_path / "accounts" / "accounts.db")
    pw, code = con.execute("select pw_hash, code_hash from account").fetchone()
    sessions = [r[0] for r in con.execute("select id_hash from session")]
    con.close()
    assert pw.startswith("scrypt$") and SIGNUP["password"] not in pw
    assert code.startswith("scrypt$") and "135790" not in code
    assert sessions and all(len(s) == 64 for s in sessions)


def test_demo_same_copy_per_browser_new_copy_elsewhere(app_env):
    with client(app_env) as c:
        a = c.post("/api/account/demo").json()
        assert a["isDemo"] is True and a["demoCode"] == "246810"
        assert a["setup"] == {"kitchen": True, "rules": True, "agent": False, "done": False}  # connect first
        connect_demo_agent(c)
        assert c.get("/api/account").json()["setup"]["done"] is True
        assert c.post("/api/account/demo").json()["id"] == a["id"]  # reload: the same copy
    with client(app_env) as other:
        assert other.post("/api/account/demo").json()["id"] != a["id"]


def test_accounts_are_isolated(app_env, ctx):
    """An order approved in one kitchen leaves the other kitchen and the local store untouched."""
    with client(app_env) as one, client(app_env) as two:
        one.post("/api/account/demo")
        connect_demo_agent(one)
        two.post("/api/account/signup", json=SIGNUP)
        local_before = len(ctx.audit.list())
        led_two = len(two.get("/api/ledger").json()["entries"])

        r = one.post("/api/demo/ask", json={"text": "1000 litres of lactose-free milk by Monday, budget 1200 euro"})
        assert r.status_code == 200, r.text
        rid = r.json()["requestId"]
        assert rid
        assert [i["id"] for i in one.get("/api/inbox").json()] == [rid]
        assert two.get("/api/inbox").json() == []
        assert two.get(f"/api/requests/{rid}").status_code == 404
        assert len(two.get("/api/ledger").json()["entries"]) == led_two
        assert len(ctx.audit.list()) == local_before
        assert one.get("/api/ledger").json()["chain"]["ok"] is True


def test_approval_code_is_per_account(app_env):
    with client(app_env) as one:
        one.post("/api/account/signup", json=SIGNUP)
        r = one.post("/api/spend-pass", json={"autoLimitCents": 50000, "hardCapCents": 200000,
                                               "diet": ["FREE_FROM_LACTOSE"], "deliverBy": "2026-11-16",
                                               "code": "246810"})
        assert r.status_code == 403  # the demo code is not this kitchen's
        r = one.post("/api/spend-pass", json={"autoLimitCents": 50000, "hardCapCents": 200000,
                                               "diet": ["FREE_FROM_LACTOSE"], "deliverBy": "2026-11-16",
                                               "code": "135790"})
        assert r.status_code == 200 and r.json()["autoLimitCents"] == 50000
        assert one.get("/api/demo").json()["codeRequired"] is True


def test_demo_controls_only_on_demo_copies(app_env):
    with client(app_env) as c:
        c.post("/api/account/signup", json=SIGNUP)
        assert c.post("/api/demo/reset").status_code == 404
    with client(app_env) as d:
        d.post("/api/account/demo")
        assert d.post("/api/demo/reset").status_code == 200


def test_steady_routes_use_the_account(app_env, ctx):
    with client(app_env) as one:
        one.post("/api/account/demo")
        r = one.post("/api/steady/S-1/renew", headers={"X-Approve-Code": "246810"})
        assert r.status_code == 200, r.text
        assert one.get("/api/steady").json()[0]["renewedAt"]
    with client(app_env) as two:
        two.post("/api/account/demo")
        assert "renewedAt" not in two.get("/api/steady").json()[0]


def test_reset_of_demo_copy_restores_it(app_env):
    with client(app_env) as c:
        c.post("/api/account/demo")
        connect_demo_agent(c)
        c.post("/api/demo/ask", json={"text": "1000 litres of lactose-free milk by Monday, budget 1200 euro"})
        assert c.get("/api/inbox").json()
        assert c.post("/api/demo/reset").status_code == 200
        assert c.get("/api/inbox").json() == []


def test_copy_comes_from_template(app_env, tmp_path):
    t = tmp_path / "template"
    seed.reset(t / "validio.db", t / "keys")
    con = sqlite3.connect(t / "validio.db")
    with con:
        con.execute("update kitchen set name = 'from the template'")
    con.close()
    accs = acc_mod.get_accounts()
    row = accs.create(name="x", email=None, password=None, customer="1", code="246810", is_demo=True)
    db, keys = accs.paths(row["id"])
    con = sqlite3.connect(db)
    assert con.execute("select name from kitchen").fetchone()[0] == "from the template"
    con.close()
    assert (keys / "kitchen-es256.json").read_text() == (t / "keys" / "kitchen-es256.json").read_text()
    assert seed.seed_token(db) != seed.seed_token(t / "validio.db")


def test_sweep_drops_old_demo_copies(app_env):
    accs = acc_mod.get_accounts()
    old = accs.create(name="old", email=None, password=None, customer="1", code="246810", is_demo=True)
    real = accs.create(name="real", email="r@example.org", password="password1", customer="1", code="111111")
    accs.update(old["id"], created_at=time.time() - 49 * 3600)
    accs.update(real["id"], created_at=time.time() - 49 * 3600)
    assert accs.sweep() == [old["id"]]
    assert accs.get(old["id"]) is None and not (accs.root / old["id"]).exists()
    assert accs.get(real["id"]) is not None


def test_no_session_on_loopback_keeps_local_kitchen(app_env, ctx):
    with client(app_env) as c:
        assert c.get("/api/inbox").status_code == 200
        assert c.get("/api/account").status_code == 401


def test_remote_caller_without_session_is_refused(app_env, monkeypatch):
    with TestClient(app_env, client=("203.0.113.9", 5000)) as c:
        assert c.get("/api/inbox").status_code == 403
        a = c.post("/api/account/demo")
        assert a.status_code == 200
        assert c.get("/api/inbox").status_code == 200


def test_settings_work_on_the_account(app_env, ctx):
    with client(app_env) as one, client(app_env) as two:
        one.post("/api/account/signup", json=SIGNUP)
        two.post("/api/account/demo")
        s = one.get("/api/settings").json()
        assert s["kitchen"]["name"] == "Kitchen A" and s["kitchen"]["customerNumber"] == "123456"
        assert s["login"]["email"] == "a@example.org"
        r = one.put("/api/settings/kitchen", json={"name": "Kitchen A2", "deliveryAddress": "Main street 1"})
        assert r.status_code == 200
        a = one.get("/api/account").json()
        assert a["name"] == "Kitchen A2" and a["deliveryAddress"] == "Main street 1"
        assert a["setup"]["kitchen"] is True and a["setup"]["rules"] is False
        assert two.get("/api/settings").json()["kitchen"]["name"] == "Hotel Espoo kitchen"
