from fastapi import APIRouter, Query

from api import match, sqllog
from api.util import ApiError, iso, lang_order, parse_as_of

router = APIRouter()

# Reference and link sections go after the prose; they rarely carry claims worth lining up.
TAIL_SECTIONS = (
    "Lähteet", "Kirjalähteet", "Verkkolähteet", "Kirjallisuutta", "Aiheesta muualla", "Katso myös",
    "Källor", "Referenser", "Noter", "Litteratur", "Externa länkar", "Se även",
    "Einzelnachweise", "Anmerkungen", "Literatur", "Weblinks", "Siehe auch",
    "References", "Notes", "Bibliography", "Further reading", "External links", "See also",
    "Примечания", "Литература", "Ссылки", "См. также",
    "Viited", "Kirjandus", "Välislingid", "Vaata ka",
)  # fmt: skip


def topic_editions(topic: str, as_of) -> dict[str, dict]:
    rows = sqllog.run_file("compare_editions", {"topic": topic, "as_of": as_of.strftime("%Y-%m-%d %H:%M:%S")})
    return {r["lang"]: r for r in rows}


def topic_langs(topic: str) -> list[str]:
    rows = sqllog.run("SELECT lang FROM page WHERE topic_id = %s", (topic,))
    if not rows:
        raise ApiError(404, "topic_not_found", f"No topic with id {topic!r}.")
    return sorted((r["lang"] for r in rows), key=lang_order)


@router.get("/api/compare")
def compare(
    topic: str,
    as_of: str | None = None,
    anchor: str = "fi",
    langs: str | None = None,
    section: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=200),
) -> dict:
    sqllog.panel("compare")
    when = parse_as_of(as_of)
    all_langs = topic_langs(topic)
    wanted = [x for x in (langs.split(",") if langs else all_langs) if x in all_langs]
    if anchor not in all_langs:
        raise ApiError(404, "edition_not_found", f"Topic {topic!r} has no {anchor!r} edition.")
    order = [anchor] + sorted({x for x in wanted if x != anchor}, key=lang_order)
    others = order[1:]
    editions = topic_editions(topic, when)

    anchors = sqllog.run_file(
        "compare_anchor",
        {
            "as_of": when.strftime("%Y-%m-%d %H:%M:%S"),
            "topic": topic,
            "anchor": anchor,
            "section": section,
            "tail": TAIL_SECTIONS,
            "limit": limit,
            "offset": offset,
        },
    )
    hs = [a["h"] for a in anchors]
    cands = match.candidates(anchor, hs, others, when, topic)
    judged = match.verdicts(anchor, hs)

    picked: dict[str, dict[str, tuple]] = {}
    for a in anchors:
        picked[a["h"]] = {lang: match.pick(cands.get(a["h"], {}).get(lang, []), judged, a["h"]) for lang in others}
    gloss_keys = [(anchor, a["h"]) for a in anchors] + [
        (lang, row["h"]) for per in picked.values() for lang, (_, row, _) in per.items() if row
    ]
    gl = match.glosses(gloss_keys)

    def rev(lang: str):
        return editions[lang]["rev_id"] if lang in editions else None

    rows = []
    for a in anchors:
        cells = {anchor: match.cell("anchor", anchor, a, rev(anchor), gl.get((anchor, a["h"])), a["text"], None)}
        for lang in others:
            status, row, verdict = picked[a["h"]][lang]
            cells[lang] = (
                match.empty_cell()
                if row is None
                else match.cell(status, lang, row, rev(lang), gl.get((lang, row["h"])), a["text"], verdict)
            )
        rows.append({"row_id": f"{anchor}:{a['page_id']}:{a['h']}", "section": a["section"], "cells": cells})

    return {
        "topic": topic,
        "as_of": iso(when),
        "anchor": anchor,
        "langs": order,
        "editions": {
            lang: {"rev_id": e["rev_id"], "rev_ts": iso(e["ts"])} for lang, e in editions.items() if lang in order
        },
        "total_rows": int(anchors[0]["total"]) if anchors else 0,
        "rows": rows,
    }
