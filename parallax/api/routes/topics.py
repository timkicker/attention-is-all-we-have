import json

from fastapi import APIRouter

from api import sqllog
from api.util import ApiError, iso

router = APIRouter()


@router.get("/api/topics")
def topics() -> dict:
    sqllog.panel("topics")
    out: dict[str, dict] = {}
    for r in sqllog.run_file("topics"):
        t = out.setdefault(
            r["topic_id"],
            {
                "topic_id": r["topic_id"],
                "label_en": r["label_en"],
                "wikidata_id": r["wikidata_id"],
                "depth": r["depth"],
                "editions": [],
            },
        )
        t["editions"].append(
            {
                "lang": r["lang"],
                "page_id": r["page_id"],
                "title": r["title"],
                "history": r["history"],
                "revisions": int(r["revisions"]),
                "first_ts": iso(r["first_ts"]),
            }
        )
    return {"topics": list(out.values())}


@router.get("/api/stats")
def stats() -> dict:
    sqllog.panel("stats")
    return {"stats": {r["k"]: json.loads(r["v"]) for r in sqllog.run_file("stats")}}


@router.get("/api/sql/{panel_id}")
def sql_panel(panel_id: str) -> dict:
    if panel_id not in sqllog.LAST:
        raise ApiError(404, "panel_not_found", f"No statements recorded for panel {panel_id!r} yet.")
    return {"panel_id": panel_id, "statements": sqllog.LAST[panel_id]}
