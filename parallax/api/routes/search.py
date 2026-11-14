"""GET /api/search?q=: Wikipedia articles by name with their Wikidata item and whether Parallax has them."""

from fastapi import APIRouter, Query, Request

from api import ratelimit, sqllog
from api.routes.ingest import rate_limited
from api.util import ApiError
from pipeline import job, wapi, wikidata

router = APIRouter()


@router.get("/api/search")
def search(request: Request, q: str = Query(..., min_length=1, max_length=200)) -> dict:
    sqllog.panel("search")
    ratelimit.check(request, "search")
    if wapi.cooldown_left() > 0:
        raise rate_limited(wapi.cooldown_left())
    try:
        found = wikidata.search(q)
    except wapi.RateLimited as e:
        raise rate_limited(e.retry_after_s) from e
    except wapi.WikiError as e:
        raise ApiError(502, "wikipedia_unavailable", "Wikipedia did not answer the search.") from e
    qids = tuple(r["qid"] for r in found) or ("",)
    loaded = {r["wikidata_id"] for r in sqllog.run("SELECT wikidata_id FROM topic WHERE wikidata_id IN %s", (qids,))}
    jobs = {r["qid"]: r["state"] for r in sqllog.run("SELECT qid, state FROM ingest_job WHERE qid IN %s", (qids,))}
    out = []
    for r in found:
        state = jobs.get(r["qid"])
        if state in ("queued", "running", "usable"):
            status = "loading"
        elif r["qid"] in loaded and state != "failed":
            status = "ready"
        elif "fi" not in r["titles"]:
            status = "no_finnish"
        else:
            status = "new"
        eta = job.estimate_s(r["en_length"], len(r["titles"])) if status == "new" else None
        out.append(
            {
                "qid": r["qid"],
                "title": r["title"],
                "description": r["description"],
                "fi_title": r["titles"].get("fi"),
                "status": status,
                "eta_s": eta,
            }
        )
    return {"results": out[:6]}
