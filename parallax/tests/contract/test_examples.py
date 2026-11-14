"""Every route in openapi.yaml has an example in contract/examples/ that matches its schema."""

import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

CONTRACT = Path(__file__).resolve().parents[2] / "contract"
SPEC = yaml.safe_load((CONTRACT / "openapi.yaml").read_text())
ROUTES = {
    "/api/health": "get",
    "/api/topics": "get",
    "/api/compare": "get",
    "/api/claim/{lang}/{page_id}/{h}/timeline": "get",
    "/api/dropped": "get",
    "/api/sources": "get",
    "/api/check": "post",
    "/api/check/recorded": "get",
    "/api/check/{run_id}": "get",
    "/api/ask": "get",
    "/api/atlas": "get",
    "/api/stats": "get",
    "/api/sql/vector": "get",
    "/api/sql/{panel_id}": "get",
    "/api/search": "get",
    "/api/ingest": "post",
    "/api/ingest/{qid}": "get",
}


def _responses():
    for path, ops in SPEC["paths"].items():
        for method, op in ops.items():
            for status, resp in op["responses"].items():
                resp = SPEC["components"]["responses"][resp["$ref"].rsplit("/", 1)[1]] if "$ref" in resp else resp
                media = resp["content"]["application/json"]
                example = media["examples"]["default"]["externalValue"]
                yield f"{method.upper()} {path} {status}", media["schema"], example


def test_routes_match_plan():
    assert {p: next(iter(ops)) for p, ops in SPEC["paths"].items()} == ROUTES


def test_every_example_file_is_referenced():
    referenced = {ex for _, _, ex in _responses()}
    on_disk = {f"examples/{p.name}" for p in (CONTRACT / "examples").glob("*.json")}
    assert referenced == on_disk


@pytest.mark.parametrize("name,schema,example", list(_responses()), ids=lambda x: x if isinstance(x, str) else "")
def test_example_matches_schema(name, schema, example):
    validator = Draft202012Validator({"components": SPEC["components"], **schema})
    data = json.loads((CONTRACT / example).read_text())
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    assert not errors, f"{name}: {errors[0].json_path}: {errors[0].message}"


def test_success_examples_carry_sql():
    for name, _, example in _responses():
        data = json.loads((CONTRACT / example).read_text())
        if name.endswith((" 200", " 202")):
            assert "sql" in data or "statements" in data, name
