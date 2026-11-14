"""Sources: references per edition at one instant, by ISBN group and web domain. Counts only, no verdict."""

import json

from fastapi import APIRouter

from api import sqllog
from api.routes.compare import topic_langs
from api.util import iso, lang_order, parse_as_of, sql_ts

router = APIRouter()


def _counts(value) -> dict[str, int]:
    data = json.loads(value) if isinstance(value, str | bytes) else (value or {})
    return {k: int(v) for k, v in sorted(data.items(), key=lambda kv: (-int(kv[1]), kv[0]))}


@router.get("/api/sources")
def sources(topic: str, as_of: str | None = None) -> dict:
    sqllog.panel("sources")
    at = parse_as_of(as_of)
    topic_langs(topic)  # 404 for an unknown topic
    rows = sqllog.run_file("sources", {"topic": topic, "as_of": sql_ts(at)})
    return {
        "as_of": iso(at),
        "editions": [
            {
                "lang": r["lang"],
                "rev_id": r["rev_id"],
                "rev_ts": iso(r["row_start"]),
                "refs": int(r["refs"]),
                "isbn": _counts(r["isbn"]),
                "domains": _counts(r["domains"]),
            }
            for r in sorted(rows, key=lambda r: lang_order(r["lang"]))
        ],
    }
