from fastapi import APIRouter

from api import match, sqllog
from api.util import MAX_TS, ApiError, iso, lang_order

router = APIRouter()


def _life(row: dict, verdict: dict | None) -> dict:
    return {
        "lang": row["lang"],
        "page_id": row["page_id"],
        "h": row["h"],
        "text": row["text"],
        "born": iso(row["row_start"]),
        "died": iso(row["row_end"]),
        "born_rev": row["born_rev"],
        "died_rev": row["died_rev"],
        "died_comment": row["died_comment"],
        "time_precision": row["time_precision"],
        "verdict": match.verdict_ref(verdict),
    }


def matched_lives(lang: str, h: str, rows: list[dict], judged: dict) -> list[tuple[dict, dict | None]]:
    """Replay Compare at every instant an edition changed: the life each instant would show, once per life."""
    by_lang: dict[str, list[dict]] = {}
    for r in rows:
        by_lang.setdefault(r["lang"], []).append(r)
    out: dict[tuple, tuple[dict, dict | None]] = {}
    for lives in by_lang.values():
        instants = sorted({x["row_start"] for x in lives} | {x["row_end"] for x in lives if x["row_end"] < MAX_TS})
        for t in instants:
            alive = sorted((x for x in lives if x["row_start"] <= t < x["row_end"]), key=lambda x: x["dist"])
            status, row, verdict = match.pick(alive, judged, h)
            if row is not None:
                out.setdefault((row["lang"], row["h"], row["row_start"]), (row, verdict))
    return list(out.values())


@router.get("/api/claim/{lang}/{page_id}/{h}/timeline")
def timeline(lang: str, page_id: int, h: str) -> dict:
    sqllog.panel("timeline")
    params = {"lang": lang, "page_id": page_id, "h": h}
    own = sqllog.run_file("timeline", params)
    if not own:
        raise ApiError(404, "claim_not_found", f"No claim {lang}:{page_id}:{h}.")
    last = own[-1]
    lives = [_life(r, None) for r in own]
    if last["topic_id"]:
        rows = sqllog.run_file("timeline_match", params | {"topic": last["topic_id"]})
        picked = matched_lives(lang, h, rows, match.verdicts(lang, [h]))
        picked.sort(key=lambda p: (lang_order(p[0]["lang"]), p[0]["row_start"]))
        lives += [_life(row, verdict) for row, verdict in picked]
    return {
        "claim": {"lang": lang, "page_id": page_id, "h": h, "text": last["text"], "section": last["section"]},
        "lives": lives,
    }
