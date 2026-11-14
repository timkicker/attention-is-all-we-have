"""The connector URL (/mcp/c/<token>/) on the synthetic set: idle expiry and tokens kept out of the logs."""

import logging
import time

import pytest
from fastapi.testclient import TestClient

from validio.api import connect
from validio.api.app import app


@pytest.fixture
def c(syn_ctx):
    with TestClient(app) as client:
        yield client


def connected(c, ctx) -> str:
    """Pair, touch the URL as an MCP client would, allow; returns the token."""
    assert c.post("/api/agent/disconnect").status_code == 200
    url = c.post("/api/agent/pair").json()["pairing"]["mcpUrl"]
    token = url.rstrip("/").rsplit("/", 1)[1]
    assert connect.connector_ctx(token, touch=True, name="Claude") is ctx
    assert c.post("/api/agent/allow").status_code == 200
    assert connect.connector_ctx(token, touch=True) is ctx
    return token


def test_an_unused_connector_url_ends_after_30_days(c, syn_ctx):
    token = connected(c, syn_ctx)
    con = connect._kcon(syn_ctx)
    con.execute("update connector set used_at = ?", (time.time() - connect.CONNECTOR_IDLE - 60,))
    con.commit()
    con.close()
    assert connect.connector_ctx(token, touch=True) is None
    assert connect.load(syn_ctx).state == "none"
    assert "unused for 30 days" in syn_ctx.audit.list()[-1].sentence


def test_a_used_connector_url_stays(c, syn_ctx):
    token = connected(c, syn_ctx)
    assert connect.connector_ctx(token, touch=True) is syn_ctx
    assert time.time() - connect._used_at(syn_ctx) < 5


def test_connector_tokens_never_reach_the_access_log():
    from validio.api.app import RedactConnector

    rec = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d',
                            ("1.2.3.4:5", "POST", "/mcp/c/s3cr3t-T0ken_x/", "1.1", 200), None)
    RedactConnector().filter(rec)
    assert "s3cr3t" not in rec.getMessage() and "/mcp/c/***/" in rec.getMessage()
