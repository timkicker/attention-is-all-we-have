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

import contextvars
import datetime as dt
import hashlib
import json
import os
import secrets
import string
from concurrent.futures import ThreadPoolExecutor

import requests

from api import sqllog
from api.util import MAX_TS, ApiError, iso, lang_order, oldid_url, sql_ts
from contract.engine import Candidate, _fixture, claim_hash, get_engine
from engine.gemini import GeminiError

MATCH = ("same", "partial")
ALPHABET = string.digits + string.ascii_lowercase
MAX_CLAIMS = 20  # statements checked per answer: each costs one judge call per edition


class ModelUnavailable(RuntimeError):
    """The model that splits or judges the answer failed after its own retries."""


def new_run_id() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(12))


def recorded_run_id(model: str | None, question: str | None, text: str) -> str:
    return hashlib.sha1(f"{model}|{question}|{text}".encode()).hexdigest()[:12]


def default_langs(topic: str | None = None) -> list[str]:
    """The editions a check labels: those of `topic`, else every edition with deep data."""
    rows = sqllog.run_file("topic_langs", {"topic": topic}) if topic else sqllog.run_file("check_langs")
    return sorted((r["lang"] for r in rows), key=lang_order)


NEAREST_K = 5  # LIMIT of the check_nearest queries


def _nearest_per_lang(name: str, vec: list[float], langs: list[str], topic: str | None) -> dict[str, list[dict]]:
    block = sqllog.query(name)
    text = "\nUNION ALL\n".join(f"({block.replace('{n}', str(i))})" for i in range(len(langs)))
    params = {"vec": json.dumps(vec), "topic": topic, **{f"lang_{i}": lang for i, lang in enumerate(langs)}}
    out: dict[str, list[dict]] = {lang: [] for lang in langs}
    for r in sqllog.run(text, params):
        out[r["lang"]].append(r)
    return out


EXACT_MAX_LIVES = 1000  # an edition of the topic with at most this many lives is searched exactly, it is quicker


def topic_sizes(topic: str) -> dict[str, int]:
    """Lives per edition of `topic` over the whole history (steers nearest; results do not depend on it)."""
    return {r["lang"]: int(r["n"]) for r in sqllog.run_file("check_topic_sizes", {"topic": topic})}


def nearest(
    vec: list[float], langs: list[str], topic: str | None = None, sizes: dict[str, int] | None = None
) -> dict[str, list[dict]]:
    """Per edition the 5 sentence lives nearest to `vec`, within `topic` when one is given.

    Within a topic, a small edition is measured exactly (every life of it); a large one goes through the vector
    index, and exactly after all when the index's nearest lives held fewer than 5 of the topic. sizes: topic_sizes,
    computed once per check."""
    if not topic:
        return _nearest_per_lang("check_nearest", vec, langs, None)
    sizes = topic_sizes(topic) if sizes is None else sizes
    big = [lang for lang in langs if sizes.get(lang, 0) > EXACT_MAX_LIVES]
    out = _nearest_per_lang("check_nearest_topic", vec, big, topic) if big else {}
    exact = [lang for lang in langs if lang not in big or len(out[lang]) < NEAREST_K]
    if exact:
        out |= _nearest_per_lang("check_nearest_topic_exact", vec, exact, topic)
    return {lang: out.get(lang, []) for lang in langs}


# The nearest search of one claim is about a second of SQL; one after the other, a 17-statement answer spent 24 s
# there. The searches only read, so a few run at once (each in a copy of the request's context, for the SQL log).
NEAREST_PARALLEL = int(os.environ.get("CHECK_NEAREST_PARALLEL", "4"))


def _nearest_all(
    vectors: list[list[float]], langs: list[str], topic: str | None, sizes: dict[str, int] | None
) -> list[dict[str, list[dict]]]:
    if len(vectors) < 2:
        return [nearest(v, langs, topic, sizes) for v in vectors]
    with ThreadPoolExecutor(max_workers=min(NEAREST_PARALLEL, len(vectors))) as pool:
        futs = [pool.submit(contextvars.copy_context().run, nearest, v, langs, topic, sizes) for v in vectors]
        return [f.result() for f in futs]


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


# seconds per embed request while a reader waits for a check: while an article loads, ollama embeds its batches
# first, and a 17-statement answer then took more than 20 s and failed
EMBED_TIMEOUT = 90


def _bge_backend(engine) -> bool:
    """Fake engine with a real bge-m3 EMBED_BACKEND (ollama, st, remote): pasted claims get vectors comparable with
    the stored sentence vectors, so the similarity guess may judge them. EMBED_BACKEND=fake or unset keeps the old
    fixture-or-random behaviour, since sketch vectors cannot be compared with bge-m3 ones."""
    return engine.name == "fake" and os.environ.get("EMBED_BACKEND") not in (None, "", "fake")


def embed_claims(engine, claims: list[str]) -> list[list[float]]:
    """Claim vectors. The fake engine answers from its fixtures; with a bge-m3 EMBED_BACKEND a claim the fixtures do
    not know is embedded with the embedder the any-article ingest uses, instead of getting a random vector."""
    table = _fixture("embed")
    unknown = [c for c in claims if claim_hash(c) not in table]
    if not _bge_backend(engine) or not unknown:
        return engine.embed(claims)
    from engine.embed import Overlay, backend, embed_texts, shared_store

    try:
        # shared_store() reads data/emb/ once per process; the claims' own vectors live only for this request
        fresh = embed_texts(unknown, Overlay(shared_store()), be=backend(timeout=EMBED_TIMEOUT))
    except (requests.ConnectionError, requests.HTTPError, requests.Timeout) as e:
        raise ApiError(
            503, "embed_unavailable", "The embedding service is not answering, so new text cannot be checked now."
        ) from e
    by_text = dict(zip(unknown, fresh, strict=True))
    return [[float(x) for x in by_text[c]] if c in by_text else engine.embed([c])[0] for c in claims]


def _judge_claim(engine, claim: str, cands: dict[str, list[dict]]) -> dict[str, list[dict]]:
    def one(lang: str) -> tuple[str, list[dict]]:
        rows = cands[lang]
        if not rows:
            return lang, []
        cs = [Candidate(r["lang"], r["page_id"], r["h"], r["text"]) for r in rows]
        if _bge_backend(engine) and claim_hash(claim) not in _fixture("embed"):
            # a pasted claim the fixtures never saw: the similarity guess, stored under its own model name
            pairs = engine.judge_or_guess(claim, "en", cs, strict=True)
        else:
            pairs = [(v, engine.model_id) for v in engine.judge(claim, "en", cs)]
        by_h = {v.h: (v, model) for v, model in pairs}
        return lang, [
            _evidence(r, by_h[r["h"]][0], by_h[r["h"]][1], engine.prompt_version) for r in rows if r["h"] in by_h
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
    topic: str | None = None,
) -> str:
    """Check one answer, store the run and return its run_id.

    Every model call happens before anything is stored, so a failing model leaves no half-stored run. Only the first
    MAX_CLAIMS statements of an answer are checked."""
    engine = get_engine()
    langs = sorted(langs or default_langs(topic), key=lang_order)
    try:
        claims = engine.split_claims(text)[:MAX_CLAIMS]
        vectors = embed_claims(engine, claims) if claims else []
        sizes = topic_sizes(topic) if topic and claims else None
        near = _nearest_all(vectors, langs, topic, sizes)
        judged_all = [_judge_claim(engine, claim, cands) for claim, cands in zip(claims, near, strict=True)]
    except GeminiError as e:
        raise ModelUnavailable(str(e)) from e
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
    for idx, (claim, vec, judged) in enumerate(zip(claims, vectors, judged_all, strict=True)):
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
