"""docs/AGENTS.md cannot drift: every JSON example is checked against the live OpenAPI schema or the
MCP server's input schema, unknown fields included, and the documented 401 is reproduced live."""

import copy
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from mcp import Client

from validio.api.app import app
from validio.api.mcp_server import server

DOC = Path(__file__).resolve().parents[3] / "docs" / "AGENTS.md"
BLOCK = re.compile(r"<!-- check: (?P<kind>[a-z]+) (?P<what>[^>]*?) -->\s*```json\n(?P<json>.*?)```", re.DOTALL)


def blocks():
    return [(m["kind"], m["what"].strip(), json.loads(m["json"])) for m in BLOCK.finditer(DOC.read_text())]


def _strict(node):
    """No field the schema does not name: a renamed field in the API breaks the doc."""
    if isinstance(node, dict):
        if "properties" in node and "additionalProperties" not in node:
            node["additionalProperties"] = False
        for v in node.values():
            _strict(v)
    elif isinstance(node, list):
        for v in node:
            _strict(v)
    return node


def _openapi_schema(method, path, part):
    spec = _strict(copy.deepcopy(app.openapi()))
    op = spec["paths"][path][method.lower()]
    node = op["requestBody"] if part == "body" else op["responses"]["200"]
    return {**node["content"]["application/json"]["schema"], "components": spec["components"]}


def test_doc_has_examples():
    kinds = [k for k, _, _ in blocks()]
    assert kinds.count("mcp") == 6 and kinds.count("response") >= 6 and "body" in kinds and "error" in kinds


@pytest.mark.parametrize("kind,what,example", [b for b in blocks() if b[0] in ("response", "body")],
                         ids=lambda v: v if isinstance(v, str) else "")
def test_http_example_matches_openapi(kind, what, example):
    method, path = what.split()
    Draft202012Validator(_openapi_schema(method, path, kind)).validate(example)


@pytest.mark.asyncio
async def test_mcp_examples_match_tool_schemas():
    async with Client(server) as c:
        schemas = {t.name: t.input_schema for t in (await c.list_tools()).tools}
    examples = {what: ex for kind, what, ex in blocks() if kind == "mcp"}
    assert set(examples) == set(schemas)
    for name, ex in examples.items():
        Draft202012Validator(_strict(copy.deepcopy(schemas[name]))).validate(ex)


def test_every_agent_route_has_an_answer():
    documented = {w for k, w, _ in blocks() if k == "response"}
    routes = {f"{m.upper()} {p}" for p, ops in app.openapi()["paths"].items() if p.startswith("/agent/v1")
              for m in ops}
    assert routes | {"POST /api/steady/{order_id}/renew"} <= documented


def test_documented_errors_are_real(ctx):
    errors = {w: ex for k, w, ex in blocks() if k == "error"}
    for ex in errors.values():
        assert set(ex) == {"detail"}
    with TestClient(app) as http:
        r = http.post("/agent/v1/requests", json={"lines": [{"text": "milk"}], "idempotencyKey": "doc"})
        assert (r.status_code, r.json()) == (401, errors["401 POST /agent/v1/requests"])
        r = http.get("/agent/v1/orders/O-99")
        assert (r.status_code, r.json()) == (404, errors["404 GET /agent/v1/orders/{order_id}"])
