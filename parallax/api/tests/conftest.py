"""API tests run against a separate database `parallax_test` with contract/schema.sql and seed-mini loaded."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pymysql
import pytest
import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
TEST_DB = "parallax_test"
SPEC = yaml.safe_load((ROOT / "contract/openapi.yaml").read_text())


def _create_test_db() -> None:
    """Create parallax_test. The app user may lack CREATE rights (CI), then root grants them."""
    from contract.db import settings

    conf = settings()
    try:
        conn = pymysql.connect(host=conf["host"], port=conf["port"], user=conf["user"], password=conf["password"])
        with conn.cursor() as c:
            c.execute(f"CREATE DATABASE IF NOT EXISTS {TEST_DB} CHARACTER SET utf8mb4")
        conn.close()
        return
    except pymysql.err.OperationalError:
        pass
    root_pw = os.environ.get("DB_ROOT_PASSWORD") or conf["password"]
    conn = pymysql.connect(host=conf["host"], port=conf["port"], user="root", password=root_pw)
    with conn.cursor() as c:
        c.execute(f"CREATE DATABASE IF NOT EXISTS {TEST_DB} CHARACTER SET utf8mb4")
        c.execute(f"GRANT ALL ON {TEST_DB}.* TO %s@'%%'", (conf["user"],))
    conn.close()


def pytest_configure(config):
    from contract.db import load_env

    load_env()
    os.environ["ENGINE"] = "fake"
    os.environ["RATE_LIMITS"] = "0"  # api/ratelimit.py: the suite sends many checks from one client
    os.environ["INGEST_MAX_ACTIVE"] = "1000"
    os.environ["INGEST_PARSE_PROCESS"] = "0"  # parse in the worker thread; pipeline/tests covers the parse process
    if os.environ.get("PARALLAX_SEED_DB"):
        # Seed checks against an already loaded database, e.g. PARALLAX_SEED=v2 PARALLAX_SEED_DB=parallax.
        os.environ["DB_NAME"] = os.environ["PARALLAX_SEED_DB"]
        os.environ["SEED"] = os.environ.get("PARALLAX_SEED", "unknown")
        return
    os.environ["DB_NAME"] = TEST_DB
    os.environ["SEED"] = "mini"
    _create_test_db()
    subprocess.run(
        [sys.executable, "scripts/load_sql.py", "--reset", "contract/schema.sql", "contract/fixtures/seed-mini.sql"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from api.main import app

    with TestClient(app) as c:
        yield c


def schema_errors(path: str, data: dict, method: str = "get", status: str = "200") -> list[str]:
    """Validate a response body against its schema in contract/openapi.yaml."""
    resp = SPEC["paths"][path][method]["responses"][status]
    if "$ref" in resp:
        resp = SPEC["components"]["responses"][resp["$ref"].rsplit("/", 1)[1]]
    schema = resp["content"]["application/json"]["schema"]
    validator = Draft202012Validator({"components": SPEC["components"], **schema})
    return [f"{e.json_path}: {e.message}" for e in validator.iter_errors(data)]


def example(name: str) -> dict:
    return json.loads((ROOT / "contract/examples" / f"{name}.json").read_text())


@pytest.fixture(autouse=True)
def _fresh_cache():
    """Tests write to the database between requests; each starts with an empty response cache."""
    from api import cache

    cache.clear()
    yield
