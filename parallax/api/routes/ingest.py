"""POST /api/ingest {qid, since?} queues an any-article ingest; GET /api/ingest/:qid reports its progress."""

import datetime as dt
import math
import re

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from api import cache, ratelimit, sqllog
from api.db import connection
from api.util import ApiError
from pipeline import job, wapi

router = APIRouter()
WORKER: job.Worker | None = None  # started by api.main
QID = re.compile(r"^Q[1-9][0-9]*$")


class IngestBody(BaseModel):
    qid: str
    since: str | None = None


def rate_limited(seconds: float) -> ApiError:
    s = max(1, math.ceil(seconds))
    err = ApiError(429, "rate_limited", "Wikipedia asked us to slow down. Try again later.")
    err.detail["retry_after_s"] = s
    err.headers = {"Retry-After": str(s)}
    return err


def _status(qid: str) -> dict | None:
    with connection() as conn, conn.cursor() as cur:
        return job.status(cur, qid)


@router.post("/api/ingest", status_code=202)
def ingest(body: IngestBody, request: Request):
    sqllog.panel("ingest")
    qid = body.qid.strip().upper()
    if not QID.match(qid):
        raise ApiError(422, "bad_qid", f"qid must look like Q123, not {body.qid!r}.")
    since = None
    if body.since:
        try:
            since = dt.date.fromisoformat(body.since).isoformat()
        except ValueError as e:
            raise ApiError(422, "bad_since", "since must be an ISO date such as 2021-01-01.") from e
    # only a queued job costs work: asking about a known one stays free, and a request that fails uses no token
    known = _status(qid)
    if known is None or known["state"] == "failed":
        ratelimit.check(request, "ingest", spend=False)
    try:
        with connection() as conn, conn.cursor() as cur:
            created = job.create(cur, qid, since, max_active=job.MAX_ACTIVE)
    except job.NoFinnish as e:
        raise ApiError(422, "no_finnish", "This article has no Finnish edition, so it cannot be loaded.") from e
    except job.IngestBusy as e:
        busy = "Other articles are loading now, one at a time. Try again in a few minutes."
        raise ratelimit.too_many(60, busy) from e
    except job.UnknownItem as e:
        raise ApiError(404, "not_found", f"No Wikidata item {qid}.") from e
    except wapi.RateLimited as e:
        raise rate_limited(e.retry_after_s) from e
    except wapi.WikiError as e:
        raise ApiError(502, "wikipedia_unavailable", "Wikidata did not answer.") from e
    if created == "queued":
        ratelimit.spend(request, "ingest")
    cache.clear(job.topic_slug(qid))  # search and the article list now say loading; other articles stay cached
    if WORKER:
        WORKER.notify()
    return JSONResponse(_status(qid), status_code=202)


@router.get("/api/ingest/{qid}")
def ingest_status(qid: str) -> dict:
    sqllog.panel("ingest")
    out = _status(qid.strip().upper())
    if out is None:
        raise ApiError(404, "not_found", f"No ingest and no topic for {qid}.")
    return out
