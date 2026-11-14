"""Ask: the sentences of each edition nearest to a question at one instant. Quotes only, nothing generated."""

import json

from fastapi import APIRouter, Query, Request

from api import match, ratelimit, sqllog
from api.util import ApiError, iso, lang_order, oldid_url, parse_as_of, sql_ts
from contract.engine import get_engine

router = APIRouter()
MAX_CHARS = 500


def _langs(langs: str | None) -> list[str]:
    known = [r["lang"] for r in sqllog.run_file("check_langs")]
    wanted = [x for x in (langs or "").split(",") if x] or known
    return sorted((x for x in wanted if x in known), key=lang_order)


@router.get("/api/ask")
def ask(
    request: Request, q: str, as_of: str | None = None, langs: str | None = None, k: int = Query(3, ge=1, le=10)
) -> dict:
    sqllog.panel("ask")
    q = q.strip()
    if not q:
        raise ApiError(422, "empty_question", "Type a question.")
    if len(q) > MAX_CHARS:
        raise ApiError(422, "question_too_long", f"The question is longer than {MAX_CHARS} characters.")
    at = parse_as_of(as_of)
    editions = _langs(langs)
    quotes: dict[str, list[dict]] = {lang: [] for lang in editions}
    if editions:
        ratelimit.check(request, "ask")
        vec = get_engine().embed([q])[0]
        block = sqllog.query("ask")
        text = "\nUNION ALL\n".join(f"({block.replace('{n}', str(i))})" for i in range(len(editions)))
        params = {"vec": json.dumps(vec), "as_of": sql_ts(at), "k": k}
        params.update({f"lang_{i}": lang for i, lang in enumerate(editions)})
        rows = sorted(sqllog.run(text, params), key=lambda r: r["dist"])
        gl = match.glosses([(r["lang"], r["h"]) for r in rows if r["lang"] != "en"])
        for r in rows:
            quotes[r["lang"]].append(
                {
                    "text": r["text"],
                    "gloss": gl.get((r["lang"], r["h"])),
                    "dist": round(float(r["dist"]), 4),
                    "born": iso(r["row_start"]),
                    "died": iso(r["row_end"]),
                    "oldid_url": oldid_url(r["lang"], r["born_rev"]),
                }
            )
    return {"q": q, "as_of": iso(at), "quotes": quotes}
