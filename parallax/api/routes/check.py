"""Check an answer: POST runs the engine and stores the run, GET replays it without the engine."""

import asyncio
import datetime as dt
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from api import checker, ratelimit, sqllog
from api.util import ApiError, parse_as_of

router = APIRouter()
MAX_CHARS = 6000


class CheckRequest(BaseModel):
    text: str = Field(min_length=1)
    as_of: str | None = None
    langs: list[str] | None = Field(default=None, max_length=16)
    topic: str | None = Field(default=None, max_length=32)  # topic_id; the evidence then comes from this topic only


class _Gate:
    """At most CHECK_PARALLEL checks run at once (each embeds its claims on the box's CPUs); up to CHECK_WAITING more
    wait their turn without holding a thread, so a room checking answers at once cannot starve the read routes of the
    threadpool. Beyond that the answer is 503 busy with Retry-After."""

    def __init__(self) -> None:
        self.parallel = int(os.environ.get("CHECK_PARALLEL", "3"))
        self.waiting_max = int(os.environ.get("CHECK_WAITING", "30"))
        self.waiting = 0
        self._sem: tuple[asyncio.AbstractEventLoop, asyncio.Semaphore] | None = None

    def _semaphore(self) -> asyncio.Semaphore:
        loop = asyncio.get_running_loop()
        if self._sem is None or self._sem[0] is not loop:  # a semaphore belongs to one loop (tests start several)
            self._sem = (loop, asyncio.Semaphore(self.parallel))
        return self._sem[1]

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        sem = self._semaphore()
        if self.waiting >= self.waiting_max:
            err = ApiError(503, "busy", "Many answers are being checked right now. Try again in a minute.")
            err.detail["retry_after_s"] = 30
            err.headers = {"Retry-After": "30"}
            raise err
        self.waiting += 1
        try:
            await sem.acquire()
        finally:
            self.waiting -= 1
        try:
            yield
        finally:
            sem.release()


GATE = _Gate()


def _validated(req: CheckRequest) -> tuple[str, dt.datetime | None, list[str]]:
    text = req.text.strip()
    if not text:
        raise ApiError(422, "empty_text", "Paste an answer to check.")
    if len(text) > MAX_CHARS:
        raise ApiError(422, "text_too_long", f"The answer is longer than {MAX_CHARS} characters.")
    as_of = parse_as_of(req.as_of) if req.as_of else None
    known = checker.default_langs(req.topic)
    if req.topic and not known:
        raise ApiError(404, "topic_not_found", f"No topic with id {req.topic!r}.")
    unknown = sorted(set(req.langs or []) - set(known))
    if unknown:
        raise ApiError(422, "bad_lang", f"No checked edition {', '.join(unknown)}; use some of {', '.join(known)}.")
    return text, as_of, req.langs or known


@router.post("/api/check")
async def check(req: CheckRequest, request: Request) -> dict:
    sqllog.panel("check")
    text, as_of, langs = await run_in_threadpool(_validated, req)
    ratelimit.check(request, "check")
    async with GATE.slot():
        try:
            run_id = await run_in_threadpool(checker.run_check, text, as_of=as_of, langs=langs, topic=req.topic)
        except checker.ModelUnavailable as e:
            raise ApiError(
                503, "model_unavailable", "The model that reads the answer is not answering. Try again later."
            ) from e
    return await run_in_threadpool(checker.load_run, run_id, as_of)


@router.get("/api/check/recorded")
def recorded() -> dict:
    sqllog.panel("check")
    rows = sqllog.run_file("check_recorded")
    return {
        "runs": [
            {
                "run_id": r["run_id"],
                "question": r["question"],
                "answer_model": r["answer_model"],
                "answer_date": r["answer_date"].isoformat() if r["answer_date"] else None,
            }
            for r in rows
        ]
    }


@router.get("/api/check/{run_id}")
def replay(run_id: str, as_of: str | None = None) -> dict:
    sqllog.panel("check")
    body = checker.load_run(run_id, parse_as_of(as_of) if as_of else None)
    if body is None:
        raise ApiError(404, "run_not_found", f"No check run {run_id}.")
    return body
