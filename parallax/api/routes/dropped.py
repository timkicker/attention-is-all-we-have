"""Dropped here, alive there: sentences one edition removed while other editions still state them."""

import json
import re

from fastapi import APIRouter, Query

from api import match, sqllog
from api.util import ApiError, iso, lang_order, oldid_url
from contract.engine import claim_hash

router = APIRouter()
REASONS = ("none", "unsourced", "error", "speculation", "other")
SCALE_KEYS = ("fi_lives", "fi_dead", "fi_dead_1y", "fi_revisions")


def _pairs() -> dict[tuple[str, str], dict[tuple[str, str], dict]]:
    """{(lang, h): {(other lang, other h): verdict}} for every same or partial verdict, both directions."""
    out: dict[tuple[str, str], dict[tuple[str, str], dict]] = {}
    for r in sqllog.run_file("dropped_verdicts"):
        v = {"label": r["label"], "model": r["model"], "prompt_version": r["prompt_version"]}
        out.setdefault((r["a_lang"], r["a_h"]), {})[(r["b_lang"], r["b_h"])] = v
        out.setdefault((r["b_lang"], r["b_h"]), {})[(r["a_lang"], r["a_h"])] = v
    return out


def alive_in(dead: dict, pairs: dict, alive: dict) -> list[dict]:
    """Current sentences of other editions the judge pairs with the dropped one, directly or through one pivot.

    A pivot is a sentence the judge paired with the dropped one (often the anchor claim of the matching run):
    whatever the judge paired with the pivot is then paired with the dropped sentence too. Through a pivot the
    label is `same` only when both steps are `same`. One sentence per edition: direct before pivot, same first.
    """
    key = (dead["lang"], dead["h"])
    found: dict[str, tuple[int, dict, dict]] = {}

    def offer(other: tuple[str, str], verdict: dict, hops: int) -> None:
        lang = other[0]
        if lang == dead["lang"] or other not in alive:
            return
        rank = hops * 2 + (verdict["label"] != "same")
        if lang not in found or rank < found[lang][0]:
            found[lang] = (rank, alive[other], verdict)

    for pivot, v1 in pairs.get(key, {}).items():
        offer(pivot, v1, 0)
        for other, v2 in pairs.get(pivot, {}).items():
            if other != key:
                label = "same" if v1["label"] == v2["label"] == "same" else "partial"
                offer(other, {**v2, "label": label}, 1)
    return [
        {
            "lang": lang,
            "h": row["h"],
            "page_id": row["page_id"],
            "text": row["text"],
            "verdict": match.verdict_ref(v),
            "oldid_url": oldid_url(lang, row["born_rev"]),
        }
        for lang, (_, row, v) in sorted(found.items(), key=lambda x: lang_order(x[0]))
    ]


TOKEN = re.compile(r"\S+")
PUNCT = ".,;:!?\"'“”„«»()[]—–-"


def _norm(word: str) -> str:
    return word.strip(PUNCT).lower()


def cut_span(text: str, after: str) -> dict | None:
    """{start, end} character range of `text` that `after` leaves out, when `after` is `text` minus one run of words.

    None when nothing or everything was cut, or when `after` changed more than one cut.
    """
    a = list(TOKEN.finditer(text))
    na = [_norm(m.group()) for m in a]
    nb = [_norm(w) for w in TOKEN.findall(after)]
    if not nb or len(nb) >= len(na):
        return None
    head = 0
    while head < len(nb) and na[head] == nb[head]:
        head += 1
    tail = 0
    while tail < len(nb) - head and na[-1 - tail] == nb[-1 - tail]:
        tail += 1
    if head + tail < len(nb):
        return None
    cut = a[head : len(a) - tail]
    if not any(na[head : len(a) - tail]):  # nothing, or only punctuation
        return None
    return {"start": cut[0].start(), "end": len(text) if tail == 0 else cut[-1].end()}


def removed_parts(topic: str, rows: list[dict]) -> dict[tuple, dict]:
    """{(lang, page_id, h): {start, end}} for dropped sentences the same edit kept with only some words cut.

    A cut of three words or more that the edit moved into another sentence of the same page does not count.
    """
    keys = tuple({(r["lang"], r["page_id"], r["row_end"]) for r in rows})
    if not keys:
        return {}
    born: dict[tuple, list[str]] = {}
    for s in sqllog.run_file("dropped_successors", {"topic": topic, "keys": keys}):
        born.setdefault((s["lang"], s["page_id"], s["row_start"]), []).append(s["text"])
    out = {}
    for r in rows:
        texts = born.get((r["lang"], r["page_id"], r["row_end"]), [])
        for t in texts:
            span = cut_span(r["text"], t)
            if span is None:
                continue
            words = [_norm(w) for w in TOKEN.findall(r["text"][span["start"] : span["end"]])]
            part = f" {' '.join(words)} "
            others = [f" {' '.join(_norm(w) for w in TOKEN.findall(o))} " for o in texts if o != t]
            moved = len(words) >= 3 and any(part in o for o in others)
            if not moved:
                out[(r["lang"], r["page_id"], r["h"])] = span
            break
    return out


def cut_words(text: str, span: dict) -> str:
    """The removed words as a sentence of their own, the text pipeline.gloss_fill glosses for a partial cut."""
    return text[span["start"] : span["end"]].strip().rstrip(",;:").strip()


def add_cut_glosses(page: list[tuple[dict, list]], cuts: dict[tuple, dict]) -> None:
    """Give each partial cut `words_en`, the English gloss of the removed words (None when there is none)."""
    keys = {}
    for r, _ in page:
        span = cuts.get((r["lang"], r["page_id"], r["h"]))
        if span is not None:
            keys[(r["lang"], r["page_id"], r["h"])] = (r["lang"], claim_hash(cut_words(r["text"], span)))
    gl = match.glosses(list(keys.values()))
    for k, g in keys.items():
        cuts[k]["words_en"] = gl.get(g)


def _row(r: dict, gloss: str | None, alive: list[dict], removed: dict | None = None) -> dict:
    return {
        "lang": r["lang"],
        "page_id": r["page_id"],
        "title": r["title"],
        "h": r["h"],
        "text": r["text"],
        "gloss": gloss,
        "born": iso(r["row_start"]),
        "died": iso(r["row_end"]),
        "died_rev": r["died_rev"],
        "died_comment": r["died_comment"],
        "days": int(r["days"]),
        "reason": r.get("reason") or "none",
        "time_precision": r["time_precision"],
        "last_rev": r["last_rev"],
        "last_url": oldid_url(r["lang"], r["last_rev"]),
        "alive_in": alive,
        "removed": removed,
    }


def scale() -> dict:
    """The Finnish scale line. Stored stat keys win (pipeline.seed_stats); only missing keys are counted."""
    stored = {r["k"]: json.loads(r["v"]) for r in sqllog.run_file("dropped_stat")}
    if all(k in stored for k in SCALE_KEYS):
        return {k: int(stored[k]) for k in SCALE_KEYS}
    (counted,) = sqllog.run_file("dropped_scale")
    return {k: int(stored[k]) if k in stored else int(counted[k]) for k in SCALE_KEYS}


def topic_rows(topic: str, lang: str | None, min_days: int) -> list[dict]:
    lives = sqllog.run_file("dropped_topic", {"topic": topic, "lang": lang, "min_days": min_days})
    latest: dict[tuple, dict] = {}
    for r in lives:  # a sentence can be dropped twice; show its last life
        k = (r["lang"], r["page_id"], r["h"])
        if k not in latest or r["row_end"] > latest[k]["row_end"]:
            latest[k] = r
    pairs = _pairs()
    wanted = {o[1] for r in latest.values() for p in pairs.get((r["lang"], r["h"]), {}) for o in [p, *pairs.get(p, {})]}
    alive = {}
    if wanted:
        for r in sqllog.run_file("dropped_alive", {"topic": topic, "hs": tuple(wanted)}):
            alive[(r["lang"], r["h"])] = r
    out = []
    for r in sorted(latest.values(), key=lambda r: (-int(r["days"]), lang_order(r["lang"]), r["h"])):
        found = alive_in(r, pairs, alive)
        if found:
            out.append((r, found))
    return out


@router.get("/api/dropped")
def dropped(
    topic: str | None = None,
    lang: str | None = None,
    reason: str | None = None,
    min_days: int = Query(365, ge=0),
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=200),
) -> dict:
    sqllog.panel("dropped")
    if reason is not None and reason not in REASONS:
        raise ApiError(422, "bad_reason", f"reason must be one of {', '.join(REASONS)}.")
    if topic:
        found = topic_rows(topic, lang, min_days)
        page = found[offset : offset + limit]
        glosses = match.glosses([(r["lang"], r["h"]) for r, _ in page])
        cuts = removed_parts(topic, [r for r, _ in page])
        add_cut_glosses(page, cuts)
        rows = [
            _row(r, glosses.get((r["lang"], r["h"])), a, cuts.get((r["lang"], r["page_id"], r["h"]))) for r, a in page
        ]
        total = len(found)
    else:
        if lang not in (None, "fi"):
            raise ApiError(422, "bad_lang", "Without a topic the list covers the Finnish edition only (lang=fi).")
        lives = sqllog.run_file(
            "dropped_fi", {"reason": reason, "min_days": min_days, "limit": limit, "offset": offset}
        )
        rows = [_row(r, None, []) for r in lives]
        total = int(lives[0]["total"]) if lives else 0
    return {"total": total, "rows": rows, "scale": scale()}
