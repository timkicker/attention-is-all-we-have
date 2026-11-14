"""Database settings shared by every track. Values come from the environment or parallax/.env."""

import os
from pathlib import Path

import pymysql

ROOT = Path(__file__).resolve().parent.parent


def load_env(path: Path = ROOT / ".env") -> None:
    """Read KEY=VALUE lines from .env into os.environ without overriding what is already set."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def settings() -> dict:
    load_env()
    return {
        "host": os.environ.get("DB_HOST") or "127.0.0.1",
        "port": int(os.environ.get("DB_PORT") or 3307),
        "user": os.environ.get("DB_USER") or "parallax",
        "password": os.environ.get("DB_PASSWORD") or "parallax",
        "database": os.environ.get("DB_NAME") or "parallax",
    }


def connect(**overrides) -> pymysql.connections.Connection:
    """A connection with the session settings every Parallax query relies on."""
    conf = settings() | overrides
    conn = pymysql.connect(charset="utf8mb4", autocommit=True, **conf)
    with conn.cursor() as c:
        c.execute("SET time_zone='+00:00'")
        c.execute("SET mhnsw_ef_search=1000")
    return conn
