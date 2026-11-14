"""VALIDIO_PUBLIC_READ=1: a stranger on the public deploy reads the UI API without the kitchen token.
Every write stays closed: the kitchen token for any POST, the 6 digit code for approve, the demo token for
the demo switches."""

import pytest
from conftest import CODE, TOKEN
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
        assert c.get("/api/spend-passes/M-1").status_code == 404  # not shown by an agent yet, but not 401


@pytest.mark.parametrize("path", WRITES)
def test_writes_without_a_token_stay_401_with_public_read(public, monkeypatch, path):
    monkeypatch.setenv("VALIDIO_PUBLIC_READ", "1")
    with stranger() as c:
        assert c.post(path, json={"code": CODE}, headers={"X-Demo-Token": TOKEN}).status_code == 401
        assert c.post(path, json={"code": CODE}, headers={"X-Kitchen-Token": "nope"}).status_code == 401
    assert public.store.requests() == []  # nothing changed


def test_approve_and_demo_still_need_code_and_demo_token(public, monkeypatch):
    monkeypatch.setenv("VALIDIO_PUBLIC_READ", "1")
    with TestClient(app, client=REMOTE, headers={"X-Kitchen-Token": KT}) as c:
        assert c.post("/api/demo/stock-out").status_code == 403
        assert c.post("/api/demo/stock-out", headers={"X-Demo-Token": "nope"}).status_code == 403
        assert c.get("/api/demo").json()["stockOut466375"] is False
        assert c.post("/api/demo/stock-out", headers={"X-Demo-Token": TOKEN}).status_code == 200


def test_public_read_is_only_the_exact_value_1(public, monkeypatch):
    monkeypatch.setenv("VALIDIO_PUBLIC_READ", "true")
    with stranger() as c:
        assert c.get("/api/inbox").status_code == 401
