"""Check an answer: POST runs the engine and stores the run, GET replays it without the engine."""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from api import checker, sqllog
from api.util import ApiError, parse_as_of

router = APIRouter()
MAX_CHARS = 6000


class CheckRequest(BaseModel):
    text: str = Field(min_length=1)
    as_of: str | None = None
    langs: list[str] | None = None


@router.post("/api/check")
def check(req: CheckRequest) -> dict:
    sqllog.panel("check")
    text = req.text.strip()
    if not text:
        raise ApiError(422, "empty_text", "Paste an answer to check.")
    if len(text) > MAX_CHARS:
        raise ApiError(422, "text_too_long", f"The answer is longer than {MAX_CHARS} characters.")
    as_of = parse_as_of(req.as_of) if req.as_of else None
    run_id = checker.run_check(text, as_of=as_of, langs=req.langs)
    return checker.load_run(run_id, as_of)


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
