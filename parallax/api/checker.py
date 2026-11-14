"""Check an answer: split it into claims, find each claim's nearest sentence lives per edition, judge them, label.

Labels per edition, at the instant `as_of` (default now):
  says            a sentence alive at as_of is the same claim, or else partly the same
  stopped_saying  no alive sentence is the same claim but one that ended before as_of was (the latest one is shown)
  contradicts     the judge found a sentence that contradicts it
  not_found       none of the above
`same` ranks before `partial`, so an edition that once said the claim and now only partly says it, with a
differing term or number, reads "stopped saying" (en Mainila: "staged" until 2009, "an incident was reported"
since). A live `partial` without any differing term or number is a rewording and still reads "says".
Every judged candidate is stored with the run, so a replay at any as_of needs no engine call.
"""

import datetime as dt
import hashlib
import json
import secrets
import string
from concurrent.futures import ThreadPoolExecutor

from api import sqllog
from api.util import MAX_TS, iso, lang_order, oldid_url, sql_ts
from contract.engine import Candidate, get_engine

MATCH = ("same", "partial")
ALPHABET = string.digits + string.ascii_lowercase


def new_run_id() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(12))


def recorded_run_id(model: str | None, question: str | None, text: str) -> str:
    return hashlib.sha1(f"{model}|{question}|{text}".encode()).hexdigest()[:12]


def default_langs() -> list[str]:
    return sorted((r["lang"] for r in sqllog.run_file("check_langs")), key=lang_order)


def nearest(vec: list[float], langs: list[str]) -> dict[str, list[dict]]:
    block = sqllog.query("check_nearest")
    text = "\nUNION ALL\n".join(f"({block.replace('{n}', str(i))})" for i in range(len(langs)))
    params = {"vec": json.dumps(vec), **{f"lang_{i}": lang for i, lang in enumerate(langs)}}
    out: dict[str, list[dict]] = {lang: [] for lang in langs}
    for r in sqllog.run(text, params):
        out[r["lang"]].append(r)
    return out


def _evidence(r: dict, verdict, model: str, prompt_version: str) -> dict:
    return {
        "lang": r["lang"],
        "page_id": r["page_id"],
        "h": r["h"],
        "text": r["text"],
        "born": iso(r["row_start"]),
        "died": iso(r["row_end"]) if r["row_end"] < MAX_TS else None,
        "died_rev": r["died_rev"],
        "died_comment": r["died_comment"],
        "dist": round(float(r["dist"]), 4),
        "verdict": {
            "label": verdict.label,
            "model": model,
            "prompt_version": prompt_version,
            "numbers": [list(x) for x in verdict.numbers],
            "terms": [list(x) for x in verdict.terms],
        },
        "oldid_url": oldid_url(r["lang"], r["born_rev"]),
    }


def _ts(value: str | None) -> dt.datetime | None:
    return dt.datetime.fromisoformat(value.replace("Z", "")) if value else None


def _no_difference(verdict: dict) -> bool:
    return "terms" in verdict and "numbers" in verdict and not verdict["terms"] and not verdict["numbers"]


REWORDED = 0.12  # cosine distance to a sentence the same revision wrote: at most this = the sentence was reworded


def _key(e: dict) -> tuple:
    return (e["lang"], e["page_id"], e["h"], e["died"])


def reworded(judged_runs: list[dict]) -> set[tuple]:
    """Keys of ended `same` or `partial` sentence lives that the ending revision only reworded (same page, near)."""
    ended = {
        _key(e)
        for judged in judged_runs
        for rows in judged.values()
        for e in rows
        if e["died"] and e["verdict"]["label"] in MATCH
    }
    if not ended:
        return set()
    keys = tuple((lang, page_id, h, sql_ts(_ts(died))) for lang, page_id, h, died in ended)
    out = set()
    for r in sqllog.run_file("check_reworded", {"keys": keys}):
        if r["dist"] is not None and float(r["dist"]) <= REWORDED:
            out.add((r["lang"], r["page_id"], r["h"], iso(r["row_end"])))
    return out


def label(judged: list[dict], as_of: dt.datetime, rewritten: set[tuple] = frozenset()) -> dict:
    """{label, evidence} for one edition from its judged candidates, at as_of.

    A `same` sentence that ended because its revision reworded it (key in `rewritten`) still counts as said.
    """
    seen = [e for e in judged if _ts(e["born"]) <= as_of]
    alive = [e for e in seen if e["died"] is None or _ts(e["died"]) > as_of or _key(e) in rewritten]
    dead = sorted((e for e in seen if e not in alive), key=lambda e: e["died"], reverse=True)

    def with_label(rows, lab):
        return [e for e in rows if e["verdict"]["label"] == lab]

    if with_label(alive, "same"):
        return {"label": "says", "evidence": with_label(alive, "same")[:3]}
    # A live partial that differs in no term or number is the same statement reworded: the edition still says it.
    # Runs stored before verdicts kept terms and numbers have no such keys and keep the old reading.
    reworded = [e for e in with_label(alive, "partial") if _no_difference(e["verdict"])]
    if with_label(dead, "same") and not reworded:
        return {"label": "stopped_saying", "evidence": with_label(dead, "same")[:1]}
    if with_label(alive, "partial"):
        return {"label": "says", "evidence": with_label(alive, "partial")[:3]}
    if with_label(dead, "partial"):
        return {"label": "stopped_saying", "evidence": with_label(dead, "partial")[:1]}
    if with_label(seen, "contradicts"):
        return {"label": "contradicts", "evidence": with_label(seen, "contradicts")[:3]}
    return {"label": "not_found", "evidence": []}


def _judge_claim(engine, claim: str, cands: dict[str, list[dict]]) -> dict[str, list[dict]]:
    def one(lang: str) -> tuple[str, list[dict]]:
        rows = cands[lang]
        if not rows:
            return lang, []
        verdicts = engine.judge(claim, "en", [Candidate(r["lang"], r["page_id"], r["h"], r["text"]) for r in rows])
        by_h = {v.h: v for v in verdicts}
        return lang, [
            _evidence(r, by_h[r["h"]], engine.model_id, engine.prompt_version) for r in rows if r["h"] in by_h
        ]

    with ThreadPoolExecutor(max_workers=min(6, len(cands) or 1)) as pool:
        return dict(pool.map(one, cands))


def run_check(
    text: str,
    as_of: dt.datetime | None = None,
    langs: list[str] | None = None,
    source: str = "live",
    answer_model: str | None = None,
    answer_date: str | None = None,
    question: str | None = None,
    run_id: str | None = None,
) -> str:
    """Check one answer, store the run and return its run_id."""
    engine = get_engine()
    langs = sorted(langs or default_langs(), key=lang_order)
    claims = engine.split_claims(text)
    vectors = engine.embed(claims) if claims else []
    run_id = run_id or new_run_id()
    sqllog.run_file(
        "check_store_run",
        {
            "run_id": run_id,
            "text": text,
            "source": source,
            "answer_model": answer_model,
            "answer_date": answer_date,
            "question": question,
            "as_of": sql_ts(as_of) if as_of else None,
            "engine": engine.name,
        },
    )
    for idx, (claim, vec) in enumerate(zip(claims, vectors, strict=True)):
        judged = _judge_claim(engine, claim, nearest(vec, langs))
        sqllog.run_file(
            "check_store_claim",
            {
                "run_id": run_id,
                "idx": idx,
                "text": claim,
                "vec": json.dumps(vec),
                "labels": json.dumps({"judged": judged}, ensure_ascii=False),
            },
        )
    return run_id


def load_run(run_id: str, as_of: dt.datetime | None = None) -> dict | None:
    rows = sqllog.run_file("check_run", {"run_id": run_id})
    if not rows:
        return None
    head = rows[0]
    at = as_of or head["as_of"] or dt.datetime.now(dt.UTC).replace(tzinfo=None)
    claims = []
    stored = [(r, json.loads(r["labels"])["judged"]) for r in rows if r["idx"] is not None]  # None: no claim
    rewritten = reworded([j for _, j in stored])
    for r, judged in stored:
        per_lang = {lang: label(judged[lang], at, rewritten) for lang in sorted(judged, key=lang_order)}
        claims.append({"idx": r["idx"], "text": r["text"], "per_lang": per_lang})
    return {
        "run_id": head["run_id"],
        "source": head["source"],
        "answer_model": head["answer_model"],
        "answer_date": head["answer_date"].isoformat() if head["answer_date"] else None,
        "question": head["question"],
        "text": head["answer"],
        "as_of": iso(at),
        "engine": head["engine"],
        "claims": claims,
    }
