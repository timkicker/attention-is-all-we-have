import json

from fastapi import APIRouter

from api import sqllog
from api.util import ApiError, iso, lang_order, parse_as_of

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


@router.get("/api/sql/vector")
def sql_vector(topic: str, as_of: str | None = None, anchor: str = "fi", limit: int = 25) -> dict:
    """Runs the vector search behind the Differences list (compare_match) for the first statements of one day,
    so Under the hood can show it even when the list itself read the precomputed table align."""
    when = parse_as_of(as_of)
    stamp = when.strftime("%Y-%m-%d %H:%M:%S")
    with sqllog.capture() as statements:
        langs = sorted((r["lang"] for r in sqllog.run("SELECT lang FROM page WHERE topic_id = %s", (topic,))), key=lang_order)
        if not langs:
            raise ApiError(404, "topic_not_found", f"No topic with id {topic!r}.")
        hs = [
            r["h"]
            for r in sqllog.run(
                "SELECT h FROM claim FOR SYSTEM_TIME AS OF TIMESTAMP %s WHERE topic_id = %s AND lang = %s ORDER BY h LIMIT %s",
                (stamp, topic, anchor, max(1, min(limit, 200))),
            )
        ]
        others = tuple(x for x in langs if x != anchor)
        if hs and others:
            params = {"anchor": anchor, "hs": tuple(hs), "langs": others, "as_of": stamp, "topic": topic, "day": when.date()}
            sqllog.run_file("compare_match", params)
    return {"panel_id": "vector", "statements": [s for s in statements if "VEC_DISTANCE" in s["text"]]}


@router.get("/api/sql/{panel_id}")
def sql_panel(panel_id: str) -> dict:
    if panel_id not in sqllog.LAST:
        raise ApiError(404, "panel_not_found", f"No statements recorded for panel {panel_id!r} yet.")
    return {"panel_id": panel_id, "statements": sqllog.LAST[panel_id]}
