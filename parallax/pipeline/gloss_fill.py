"""English glosses for every sentence the UI can show that has none yet.

The UI shows sentences in English. pipeline.gloss covers claims alive today; this fills the rest, collected
through the API itself (in process), so the set is exactly what the pages ask for:
  (a) every row of /api/dropped for the topic, the removed words of a partial cut, and the sentences still
      alive elsewhere,
  (b) /api/compare at today and at the As-of quick picks (web/src/lib/ui/AsOf.svelte): Finnish versions and
      the matched sentences of the other editions,
  (c) the /api/claim/.../timeline entries of each statement the Differences list shows on those dates
      (a contradicting match, or a partial match that names a number or term).
English sentences are skipped: the UI shows their own text. Already glossed sentences are skipped, so a rerun
resumes where the last one stopped. `--dry-run` only counts and estimates the cost.

    set -a; . ~/.config/validio-gemini.env; set +a; ENGINE=real uv run python -m pipeline.gloss_fill --topic winterwar
"""

import argparse
import gzip
import math
import os

from api.routes.dropped import cut_words
from contract.db import connect
from contract.engine import claim_hash

DATES = [None, "2020-01-01", "2015-01-01", "2010-01-01", "2008-01-01"]  # AsOf.svelte quick picks, None = today
BATCH = 20  # sentences per model call, as in engine.real.GeminiEngine.gloss
# Rough price of the flash model in USD per million tokens, and about 3.5 characters per token.
PRICE_IN, PRICE_OUT, CHARS_PER_TOKEN, PROMPT_TOKENS = 0.30, 2.50, 3.5, 300


def _get(client, url: str, **params) -> dict:
    r = client.get(url, params={k: v for k, v in params.items() if v is not None})
    r.raise_for_status()
    return r.json()


def _real(word) -> bool:
    return bool(word) and str(word).strip() not in ("", "?")


def differs(cell: dict) -> bool:
    """Same rule as kindOf in web/src/lib/adapt/topic.ts: contradicts, or partial with a named number or term."""
    v = cell.get("verdict") or {}
    if cell.get("status") != "matched":
        return False
    if v.get("label") == "contradicts":
        return True
    named = [m for m in cell.get("marks") or [] if _real(m.get("this")) and _real(m.get("other"))]
    return v.get("label") == "partial" and bool(named)


def collect(client, topic: str, scope: str) -> dict[str, dict[tuple[str, str], str]]:
    """{part: {(lang, h): text}} of sentences the UI can show, before dropping the glossed ones."""
    parts: dict[str, dict[tuple[str, str], str]] = {"dropped": {}, "compare": {}, "timeline": {}}

    def add(part: str, lang: str | None, h: str | None, text: str | None) -> None:
        if lang and h and text and lang != "en":
            parts[part].setdefault((lang, h), text)

    offset = 0
    while True:
        d = _get(client, "/api/dropped", topic=topic, offset=offset, limit=200)
        for r in d["rows"]:
            add("dropped", r["lang"], r["h"], r["text"])
            if r.get("removed"):  # a partial cut: its removed words get a gloss of their own
                words = cut_words(r["text"], r["removed"])
                add("dropped", r["lang"], claim_hash(words), words)
            for a in r["alive_in"]:
                add("dropped", a["lang"], a["h"], a["text"])
        offset += 200
        if offset >= d["total"]:
            break

    dates = [None] if scope == "today" else DATES
    statements: set[tuple[str, int, str]] = set()
    for date in dates:
        offset = 0
        while True:
            c = _get(client, "/api/compare", topic=topic, anchor="fi", as_of=date, offset=offset, limit=200)
            for row in c["rows"]:
                a = row["cells"].get("fi") or {}
                others = [cell for lang, cell in row["cells"].items() if lang != "fi"]
                shown = any(differs(cell) for cell in others)
                if scope == "today" and not shown:
                    continue
                add("compare", "fi", a.get("h"), a.get("text"))
                for lang, cell in row["cells"].items():
                    if lang != "fi" and cell.get("status") == "matched":
                        add("compare", lang, cell.get("h"), cell.get("text"))
                if shown and a.get("h") and a.get("page_id") is not None:
                    statements.add(("fi", int(a["page_id"]), a["h"]))
            offset += 200
            if offset >= c["total_rows"]:
                break

    for lang, page_id, h in sorted(statements):
        t = _get(client, f"/api/claim/{lang}/{page_id}/{h}/timeline")
        for life in t["lives"]:
            add("timeline", life["lang"], life["h"], life["text"])
    print(f"differences statements: {len(statements)} over {len(dates)} dates", flush=True)
    return parts


def glossed(cur, keys) -> set[tuple[str, str]]:
    hs = sorted({h for _, h in keys})
    have = set()
    for i in range(0, len(hs), 1000):
        chunk = hs[i : i + 1000]
        cur.execute(f"SELECT lang, h FROM gloss WHERE h IN ({','.join(['%s'] * len(chunk))})", chunk)
        have |= {(lang, h) for lang, h in cur.fetchall()}
    return have


def estimate(todo: dict[str, dict[str, str]]) -> tuple[int, float]:
    calls = sum(math.ceil(len(v) / BATCH) for v in todo.values())
    chars = sum(len(t) for v in todo.values() for t in v.values())
    tokens_in = calls * PROMPT_TOKENS + chars / CHARS_PER_TOKEN
    tokens_out = chars / CHARS_PER_TOKEN * 1.2  # English output plus JSON
    return calls, (tokens_in * PRICE_IN + tokens_out * PRICE_OUT) / 1e6


def run(topic: str, dry_run: bool, scope: str) -> None:
    from fastapi.testclient import TestClient

    from api.main import app

    with TestClient(app) as client:
        parts = collect(client, topic, scope)
    conn = connect()
    cur = conn.cursor()
    seen: set[tuple[str, str]] = set()
    todo: dict[str, dict[str, str]] = {}
    for part, found in parts.items():
        have = glossed(cur, found)
        new = {k: t for k, t in found.items() if k not in have and k not in seen}
        seen |= set(found)
        done = len(found) - len(new)
        print(f"{part}: {len(found)} non-English sentences, {done} glossed or counted, {len(new)} to gloss")
        for (lang, h), t in new.items():
            todo.setdefault(lang, {})[h] = t
    total = sum(len(v) for v in todo.values())
    calls, usd = estimate(todo)
    by_lang = " ".join(f"{lang}={len(v)}" for lang, v in sorted(todo.items()))
    print(f"to gloss: {total} ({by_lang}), model calls about {calls}, estimated cost {usd:.2f} USD")
    if dry_run or not total:
        return

    from contract.engine import get_engine
    from engine import gemini

    if os.environ.get("ENGINE") != "real":
        raise SystemExit("set ENGINE=real to gloss (the fake engine only knows its fixtures)")
    eng = get_engine()
    model = getattr(eng, "model_id", "real")
    done = failed = 0
    for lang, items in todo.items():
        rows = list(items.items())
        for i in range(0, len(rows), BATCH):
            chunk = rows[i : i + BATCH]
            try:
                out = eng.gloss([t for _, t in chunk], lang)
            except gemini.GeminiError as e:
                failed += len(chunk)
                print(f"  {lang}: batch failed ({e}), rerun to retry", flush=True)
                continue
            cur.executemany(
                "INSERT IGNORE INTO gloss (lang, h, text_en, model) VALUES (%s,%s,%s,%s)",
                [(lang, h, g, model) for (h, _), g in zip(chunk, out, strict=True)],
            )
            conn.commit()
            done += len(chunk)
        print(f"  {lang}: {len(rows)} {gemini.stats_line()}", flush=True)
    print(f"glossed={done} failed={failed} model calls={gemini.STATS['calls']} estimated cost {usd:.2f} USD")


def dump(topic: str, path: str) -> None:
    """Write the topic's gloss rows as INSERT IGNORE statements, for scripts/load_sql.py on another server."""
    from pymysql.converters import escape_string

    cur = connect().cursor()
    cur.execute(
        "SELECT g.lang, g.h, g.text_en, g.model FROM gloss g WHERE EXISTS "
        "(SELECT 1 FROM claim FOR SYSTEM_TIME ALL c WHERE c.topic_id=%s AND c.lang=g.lang AND c.h=g.h) "
        # the removed words of partial cuts are glossed under their own hash, which no claim has
        "OR NOT EXISTS (SELECT 1 FROM claim FOR SYSTEM_TIME ALL c WHERE c.lang=g.lang AND c.h=g.h) "
        "ORDER BY g.lang, g.h",
        (topic,),
    )
    rows = cur.fetchall()
    with gzip.open(path, "wt", encoding="utf-8") as f:
        f.write(f"-- gloss rows of topic {topic}: {len(rows)}\n")
        for i in range(0, len(rows), 200):
            vals = ",\n".join(
                "('" + "','".join(escape_string(str(x)) for x in r) + "')" for r in rows[i : i + 200]
            )
            f.write(f"INSERT IGNORE INTO gloss (lang, h, text_en, model) VALUES\n{vals};\n")
    print(f"wrote {len(rows)} gloss rows to {path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", default="winterwar")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--scope", choices=["all", "today"], default="all",
        help="today = dropped rows and today's Differences statements only (the narrow scope)",
    )
    ap.add_argument("--dump", metavar="FILE", help="write the topic's gloss rows to FILE (.sql.gz) and stop")
    a = ap.parse_args()
    if a.dump:
        dump(a.topic, a.dump)
    else:
        run(a.topic, a.dry_run, a.scope)
