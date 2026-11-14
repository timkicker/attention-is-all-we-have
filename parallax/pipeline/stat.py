"""Numbers for the scale line and the docs: the stat table (k -> JSON)."""

import json


def put(cur, k: str, v) -> None:
    cur.execute(
        "INSERT INTO stat (k, v, computed_at) VALUES (%s, %s, UTC_TIMESTAMP(6)) "
        "ON DUPLICATE KEY UPDATE v=VALUES(v), computed_at=VALUES(computed_at)",
        (k, json.dumps(v, ensure_ascii=False, default=str)),
    )


def get(cur, k: str):
    cur.execute("SELECT v FROM stat WHERE k=%s", (k,))
    row = cur.fetchone()
    return json.loads(row[0]) if row else None
