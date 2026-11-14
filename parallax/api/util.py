"""Small helpers shared by the routes."""

import datetime as dt
import re

from fastapi import HTTPException

LANG_ORDER = ("fi", "sv", "de", "en", "ru", "et", "uk")
MAX_TS = dt.datetime(2038, 1, 1)  # row_end of a current row is 2038-01-19


class ApiError(HTTPException):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(status_code=status, detail={"code": code, "message": message})


def iso(ts: dt.datetime | None) -> str | None:
    """UTC ISO 8601 with Z, None for a missing or open end."""
    if ts is None or ts >= MAX_TS:
        return None
    return ts.replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def oldid_url(lang: str, rev_id: int | None) -> str | None:
    return f"https://{lang}.wikipedia.org/w/index.php?oldid={rev_id}" if rev_id else None


_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_as_of(value: str | None) -> dt.datetime:
    """ISO date or datetime (UTC), default now. AS OF needs a full datetime, so a date becomes midnight."""
    if not value:
        return dt.datetime.now(dt.UTC).replace(tzinfo=None, microsecond=0)
    try:
        if _DATE.match(value):
            return dt.datetime.fromisoformat(value + "T00:00:00")
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as e:
        raise ApiError(422, "bad_as_of", f"as_of must be an ISO date or datetime, not {value!r}.") from e
    if parsed.tzinfo:
        parsed = parsed.astimezone(dt.UTC).replace(tzinfo=None)
    return parsed


def sql_ts(value: dt.datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


def lang_order(lang: str) -> int:
    return LANG_ORDER.index(lang) if lang in LANG_ORDER else len(LANG_ORDER)
