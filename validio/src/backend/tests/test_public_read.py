"""VALIDIO_PUBLIC_READ=1: a stranger on the public deploy reads the UI API without the kitchen token.
Every write stays closed: the kitchen token (or a kitchen's session) for any POST, the 6 digit code for approve,
renew and the limits. The demo token is gone: the demo switches answer a demo copy's session only."""

import pytest
from conftest import CODE
from fastapi.testclient import TestClient

from validio.api.app import app

REMOTE = ("203.0.113.7", 50000)
KT = "kt-secret"
READS = ("/api/inbox", "/api/ledger", "/api/ledger/head", "/api/demo", "/api/steady")
WRITES = ("/api/orders/O-1/approve", "/api/orders/O-1/reject", "/api/demo/stock-out", "/api/demo/reset",
          "/api/steady/S-1/renew", "/api/steady/S-1/lines/464306/accept")


@pytest.fixture
def public(ctx, monkeypatch):
    monkeypatch.setenv("VALIDIO_PUBLIC", "1")
    monkeypatch.setenv("VALIDIO_KITCHEN_TOKEN", KT)
    return ctx


def stranger():
    return TestClient(app, client=REMOTE)


def test_reads_need_the_token_without_public_read(public):
    with stranger() as c:
        for path in READS:
            assert c.get(path).status_code == 401, path


def test_reads_are_open_with_public_read(public, monkeypatch):
    monkeypatch.setenv("VALIDIO_PUBLIC_READ", "1")
    with stranger() as c:
        for path in READS:
            assert c.get(path).status_code == 200, path
        assert c.get("/api/orders/NOPE").status_code == 404  # open, so a missing order is a plain 404
        assert c.get("/api/spend-passes/M-1").status_code == 200  # the issued pass, before any agent showed it
        assert c.get("/api/spend-passes/M-9").status_code == 404


@pytest.mark.parametrize("path", WRITES)
def test_writes_without_a_token_stay_401_with_public_read(public, monkeypatch, path):
    monkeypatch.setenv("VALIDIO_PUBLIC_READ", "1")
    with stranger() as c:
        assert c.post(path, json={"code": CODE}).status_code == 401
        assert c.post(path, json={"code": CODE}, headers={"X-Demo-Token": "nope"}).status_code == 401
        assert c.post(path, json={"code": CODE}, headers={"X-Kitchen-Token": "nope"}).status_code == 401
    assert public.store.requests() == []  # nothing changed


def test_demo_switches_stay_closed_to_the_kitchen_token(public, monkeypatch):
    monkeypatch.setenv("VALIDIO_PUBLIC_READ", "1")
    with TestClient(app, client=REMOTE, headers={"X-Kitchen-Token": KT}) as c:
        assert c.post("/api/demo/stock-out").status_code == 403
        assert c.post("/api/demo/stock-out", headers={"X-Demo-Token": "anything"}).status_code == 403
        assert c.post("/api/demo/reset").status_code == 403
        assert c.get("/api/demo").json()["stockOut466375"] is False


def test_public_read_is_only_the_exact_value_1(public, monkeypatch):
    monkeypatch.setenv("VALIDIO_PUBLIC_READ", "true")
    with stranger() as c:
        assert c.get("/api/inbox").status_code == 401



def test_a_header_named_demo_token_opens_nothing(public, monkeypatch):
    monkeypatch.setenv("VALIDIO_PUBLIC_READ", "1")
    with TestClient(app, client=REMOTE, headers={"X-Demo-Token": "demo-test-token"}) as c:
        assert c.post("/api/demo/stock-out").status_code == 401
        assert c.post("/api/demo/ask", json={"text": "1500 litres of lactose-free milk by Monday"}).status_code == 401
        assert c.post("/api/spend-pass", json={"autoLimitCents": 1, "hardCapCents": 2,
                                               "deliverBy": "2026-11-16"}).status_code == 401
    assert public.store.requests() == []


def test_a_demo_copy_drives_the_demo_on_a_public_deploy(public, monkeypatch, tmp_path):
    """What the demo token did, a demo session does now: switches, ask, and approve with 246810."""
    from validio.api import accounts as acc_mod

    monkeypatch.setenv("VALIDIO_PUBLIC_READ", "1")
    monkeypatch.setenv("VALIDIO_ACCOUNTS", str(tmp_path / "accounts"))
    monkeypatch.setenv("VALIDIO_TEMPLATE", str(tmp_path / "template"))
    acc_mod._tries.clear()
    with stranger() as c:
        assert c.post("/api/account/demo").status_code == 200
        assert c.post("/api/demo/stock-out").status_code == 200
        assert c.post("/api/demo/stock-out", json={"on": False}).status_code == 200
        assert c.post("/api/demo/reset").status_code == 200
    assert public.store.requests() == []  # the local kitchen did not move
