"""Cross-edition matching shared by Compare and the timeline: candidates, verdicts and the pick per edition."""

import datetime as dt
import json

from api import sqllog
from api.marks import marks_for
from api.util import iso, oldid_url

MATCHED = ("same", "partial", "contradicts")  # the judge says both sentences are about the same claim


def candidates(anchor: str, hs: list[str], langs: list[str], as_of: dt.datetime, topic: str) -> dict:
    """{src_h: {lang: [candidate rows by rank]}} from table align when it holds that date, else one exact query."""
    out: dict[str, dict[str, list[dict]]] = {}
    if not hs or not langs:
        return out
    params = {
        "anchor": anchor,
        "hs": tuple(hs),
        "langs": tuple(langs),
        "as_of": as_of.strftime("%Y-%m-%d %H:%M:%S"),
        "topic": topic,
        "day": as_of.date(),
    }
    (cached,) = sqllog.run_file("compare_align_dates", params)
    rows = sqllog.run_file("compare_align" if cached["n"] else "compare_match", params)
    for r in rows:
        out.setdefault(r["src_h"], {}).setdefault(r["lang"], []).append(r)
    return out


def verdicts(anchor: str, hs: list[str]) -> dict[tuple[str, str, str], dict]:
    """{(src_h, other_lang, other_h): verdict dict with numbers and terms oriented anchor -> other}."""
    out = {}
    if not hs:
        return out
    for r in sqllog.run_file("compare_verdicts", {"anchor": anchor, "hs": tuple(hs)}):
        numbers = json.loads(r["numbers"]) if r["numbers"] else []
        terms = json.loads(r["terms"]) if r["terms"] else []
        if r["a_lang"] == anchor and r["a_h"] in hs:
            key = (r["a_h"], r["b_lang"], r["b_h"])
        else:
            key = (r["b_h"], r["a_lang"], r["a_h"])
            numbers = [[b, a] for a, b in numbers]
            terms = [[b, a] for a, b in terms]
        out[key] = {
            "label": r["label"],
            "model": r["model"],
            "prompt_version": r["prompt_version"],
            "numbers": numbers,
            "terms": terms,
        }
    return out


def glosses(rows: list[tuple[str, str]]) -> dict[tuple[str, str], str]:
    hs = tuple({h for _, h in rows})
    if not hs:
        return {}
    wanted = set(rows)
    return {
        (r["lang"], r["h"]): r["text_en"]
        for r in sqllog.run_file("glosses", {"hs": hs})
        if (r["lang"], r["h"]) in wanted
    }


def pick(cands: list[dict], judged: dict, src_h: str, top: int = 5) -> tuple[str, dict | None, dict | None]:
    """(status, row, verdict). Best ranked candidate the judge pairs with the claim; else the nearest unjudged one.

    `cands` is sorted by distance. A verdict counts wherever its candidate ranks (the judge read both sentences);
    an unjudged candidate only counts within the first `top`.
    """
    if not cands:
        return "not_found", None, None
    for c in cands:
        v = judged.get((src_h, c["lang"], c["h"]))
        if v and v["label"] in MATCHED:
            return "matched", c, v
    for c in cands[:top]:
        if (src_h, c["lang"], c["h"]) not in judged:
            return "candidate", c, None
    return "not_found", None, None


def verdict_ref(v: dict | None) -> dict | None:
    return {"label": v["label"], "model": v["model"], "prompt_version": v["prompt_version"]} if v else None


def empty_cell() -> dict:
    return {
        "status": "not_found",
        "h": None,
        "page_id": None,
        "text": None,
        "gloss": None,
        "dist": None,
        "verdict": None,
        "marks": [],
        "born": None,
        "died": None,
        "born_rev": None,
        "died_rev": None,
        "time_precision": None,
        "oldid_url": None,
    }


def cell(
    status: str, lang: str, row: dict, rev_id: int | None, gloss: str | None, anchor_text: str, verdict: dict | None
) -> dict:
    return {
        "status": status,
        "h": row["h"],
        "page_id": row["page_id"],
        "text": row["text"],
        "gloss": gloss,
        "dist": round(float(row["dist"]), 4) if row.get("dist") is not None else None,
        "verdict": verdict_ref(verdict),
        "marks": [] if status == "anchor" else marks_for(anchor_text, row["text"], verdict),
        "born": iso(row["row_start"]),
        "died": iso(row["row_end"]),
        "born_rev": row["born_rev"],
        "died_rev": row["died_rev"],
        "time_precision": row["time_precision"],
        "oldid_url": oldid_url(lang, rev_id or row["born_rev"]),
    }
