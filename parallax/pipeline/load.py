"""A7: load a topic (pages, revisions, section versions, claim lives with vectors, terms) into MariaDB.

History rows go in with system_versioning_insert_history=1 and explicit row_start/row_end, current rows with
row_start only. Batches are cut by size (at most 500 rows and about 4 MB) so long rows never exceed
max_allowed_packet. `make load` resets the schema first, so a reload is idempotent.

`make reload` (--replace) keeps the rest of a restored seed (M lives, atlas, align, verdicts, glosses) and swaps only
this topic's rows: history rows of a system-versioned table cannot be deleted one by one, so each such table is copied
without the topic's rows (history included) and renamed back.
"""

import argparse
import json
import re
import time
from collections.abc import Iterable

import numpy as np
import yaml

from contract.db import connect
from contract.engine import claim_hash
from engine.embed import VectorStore
from pipeline.fetch import DATA, ROOT, hist_dir, read_jsonl, topics
from pipeline.lives import extra_path, lives_dir

MAX_ROWS = 500
MAX_BYTES = 4 * 1024 * 1024


def _size(row: tuple) -> int:
    return sum(len(v) if isinstance(v, (str, bytes)) else 8 for v in row)


def batches(rows: Iterable[tuple], max_rows: int = MAX_ROWS, max_bytes: int = MAX_BYTES):
    """Chunks of rows with at most max_rows rows and at most max_bytes of values."""
    cur, size = [], 0
    for r in rows:
        s = _size(r)
        if cur and (len(cur) >= max_rows or size + s > max_bytes):
            yield cur
            cur, size = [], 0
        cur.append(r)
        size += s
    if cur:
        yield cur


def insert(cur, table: str, cols: list[str], rows: Iterable[tuple]) -> int:
    sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})"
    n = 0
    for chunk in batches(rows):
        cur.executemany(sql, chunk)
        n += len(chunk)
    return n


def versioned(cur, table: str, cols: list[str], rows: list[dict]) -> int:
    """History rows (row_end set) first, then current rows."""
    hist = [tuple(r[c] for c in cols) + (r["row_start"], r["row_end"]) for r in rows if r["row_end"]]
    now = [tuple(r[c] for c in cols) + (r["row_start"],) for r in rows if not r["row_end"]]
    n = insert(cur, table, cols + ["row_start", "row_end"], hist)
    return n + insert(cur, table, cols + ["row_start"], now)


def _cut(s: str | None, n: int) -> str | None:
    return s[:n] if s else s


def load_terms(cur) -> tuple[int, list[tuple[str, str, re.Pattern]]]:
    spec = yaml.safe_load((ROOT / "pipeline" / "terms.yaml").read_text(encoding="utf-8"))
    rows, pats = [], []
    for term_id, t in spec["terms"].items():
        for lang, pattern in t.items():
            if lang == "gloss_en":
                continue
            rows.append((term_id, lang, pattern, spec["concept"], t["gloss_en"]))
            pats.append((term_id, lang, re.compile(pattern, re.I)))
    cur.execute("DELETE FROM term WHERE concept=%s", (spec["concept"],))
    insert(cur, "term", ["term_id", "lang", "pattern", "concept", "gloss_en"], rows)
    return len(rows), [(tid, lang, rx) for tid, lang, rx in pats] + [("__anchor__", "*", re.compile(spec["anchor"]))]


NEAR = 3  # sentences before or after an anchor sentence that still speak about the anchored incident
NEVER = "9999-12-31"


def near_anchor(sections: Iterable[dict], anchor: re.Pattern, window: int = NEAR) -> dict[str, list[tuple]]:
    """claim hash -> periods in which that sentence stood within `window` sentences of an anchor sentence of the same
    section version. Editions often name the incident in one sentence and characterise it in the next (issue #31)."""
    out: dict[str, list[tuple]] = {}
    for s in sections:
        lines = s["text"].split("\n")
        at = [i for i, line in enumerate(lines) if anchor.search(line)]
        if not at:
            continue
        span = (s["row_start"], s["row_end"] or NEVER)
        for j, line in enumerate(lines):
            if any(abs(j - i) <= window for i in at):
                out.setdefault(claim_hash(line), []).append(span)
    return out


def anchored(lv: dict, near: dict[str, list[tuple]]) -> bool:
    """The life stood near an anchor sentence at some time while it was alive."""
    start, end = lv["row_start"], lv["row_end"] or NEVER
    return any(a < end and start < b for a, b in near.get(lv["h"], ()))


VERSIONED_TOPIC_TABLES = ("section_text", "claim", "term_hit")


def drop_topic(cur, topic_id: str) -> None:
    """Remove every row (current and history) of one topic, keeping all other rows of the same tables."""
    cur.execute(
        "DELETE r FROM revision r JOIN page p ON p.lang=r.lang AND p.page_id=r.page_id WHERE p.topic_id=%s", (topic_id,)
    )
    cur.execute("DELETE FROM page WHERE topic_id=%s", (topic_id,))
    for t in VERSIONED_TOPIC_TABLES:
        cur.execute(f"SHOW COLUMNS FROM {t}")
        cols = ", ".join(f"`{r[0]}`" for r in cur.fetchall())
        cur.execute(f"DROP TABLE IF EXISTS {t}_keep")
        cur.execute(f"CREATE TABLE {t}_keep LIKE {t}")
        cur.execute(
            f"INSERT INTO {t}_keep ({cols}) SELECT {cols} FROM {t} FOR SYSTEM_TIME ALL WHERE NOT (topic_id <=> %s)",
            (topic_id,),
        )
        cur.execute(f"DROP TABLE {t}")
        cur.execute(f"RENAME TABLE {t}_keep TO {t}")


def run(topic_id: str, replace: bool = False) -> dict:
    topic = topics()[topic_id]
    pages = json.loads((hist_dir(topic_id) / "pages.json").read_text(encoding="utf-8"))
    store = VectorStore()
    conn = connect()
    conn.autocommit(False)
    cur = conn.cursor()
    timings: dict[str, float] = {}
    counts: dict[str, dict] = {}
    cur.execute("SET time_zone='+00:00'")
    cur.execute("SET system_versioning_insert_history=1")
    cur.execute("SET unique_checks=0")
    if replace:
        t_drop = time.time()
        drop_topic(cur, topic_id)
        conn.commit()
        print(f"dropped {topic_id} rows in {time.time() - t_drop:.1f}s")

    t = time.time()
    cur.execute(
        "INSERT INTO topic (topic_id, wikidata_id, label_en, depth) VALUES (%s,%s,%s,'deep') "
        "ON DUPLICATE KEY UPDATE label_en=VALUES(label_en), depth='deep'",
        (topic_id, topic["wikidata"], topic["label_en"]),
    )
    n_terms, pats = load_terms(cur)
    anchor = pats.pop()[2]
    conn.commit()

    missing_vec = 0
    for lang, page in pages.items():
        t_lang = time.time()
        pid = page["page_id"]
        cur.execute(
            "INSERT INTO page (lang, page_id, topic_id, title, source, history) VALUES (%s,%s,%s,%s,%s,%s)",
            (lang, pid, topic_id, page["title"], page["source"], page["history"]),
        )
        meta = list(read_jsonl(hist_dir(topic_id) / f"{lang}.meta.jsonl.gz"))
        if page["history"] == "every":
            parsed = {r["rev_id"] for r in meta}
        else:  # yearly snapshots plus the revisions bisect parsed around each demo edit
            parsed = {r["rev_id"] for r in read_jsonl(hist_dir(topic_id) / f"{lang}.snap.jsonl.gz")}
            if extra_path(topic_id, lang).exists():
                parsed |= {r["rev_id"] for r in read_jsonl(extra_path(topic_id, lang))}
        n_rev = insert(
            cur,
            "revision",
            ["lang", "rev_id", "page_id", "parent_id", "ts", "bytes", "minor", "comment", "snapshot"],
            (
                (
                    lang,
                    r["rev_id"],
                    pid,
                    r.get("parent_id") or None,
                    r["ts"].replace("T", " ").rstrip("Z"),
                    r.get("bytes"),
                    r.get("minor", 0),
                    _cut(r.get("comment"), 1000),
                    int(r["rev_id"] in parsed),
                )
                for r in meta
            ),
        )
        secs = [
            {**s, "topic_id": topic_id, "lang": lang, "section": s["section"][:255]}
            for s in read_jsonl(lives_dir() / f"{topic_id}-{lang}.sections.jsonl.gz")
        ]
        n_sec = versioned(cur, "section_text", ["topic_id", "lang", "section", "rev_id", "n_sent", "text"], secs)
        near = near_anchor(secs, anchor)

        claims, hits = [], []
        for lv in read_jsonl(lives_dir() / f"{topic_id}-{lang}.jsonl.gz"):
            v = store.get(lv["h"])
            if v is None:
                missing_vec += 1
                continue
            row = {
                **lv,
                "lang": lang,
                "page_id": pid,
                "topic_id": topic_id,
                "section": lv["section"][:255],
                "died_comment": _cut(lv["died_comment"], 1000),
                "emb": np.asarray(v, dtype="<f4").tobytes(),
            }
            claims.append(row)
            if anchored(lv, near):
                for tid, tlang, rx in pats:
                    if tlang == lang and rx.search(lv["text"]):
                        hits.append(
                            {
                                "topic_id": topic_id,
                                "lang": lang,
                                "term_id": tid,
                                "h": lv["h"],
                                "row_start": lv["row_start"],
                                "row_end": lv["row_end"],
                            }
                        )
        cols = [
            "lang",
            "page_id",
            "h",
            "topic_id",
            "section",
            "text",
            "born_rev",
            "died_rev",
            "died_comment",
            "time_precision",
            "has_ref",
            "had_ref",
            "emb",
        ]
        n_claim = versioned(cur, "claim", cols, claims)
        n_hit = versioned(cur, "term_hit", ["topic_id", "lang", "term_id", "h"], hits)
        conn.commit()
        timings[lang] = round(time.time() - t_lang, 2)
        counts[lang] = {"revisions": n_rev, "sections": n_sec, "claims": n_claim, "term_hits": n_hit}
        print(
            f"{lang:4} revisions={n_rev:5} sections={n_sec:5} claims={n_claim:6} term_hits={n_hit:3} "
            f"{timings[lang]:.1f}s"
        )
    total = round(time.time() - t, 1)
    print(f"terms={n_terms} missing_vectors={missing_vec} load_seconds={total}")
    out = {
        "topic": topic_id,
        "seconds": total,
        "per_lang_seconds": timings,
        "counts": counts,
        "missing_vectors": missing_vec,
    }
    (DATA / "lives" / f"{topic_id}-load.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    cur.close()
    conn.close()
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", default="winterwar")
    ap.add_argument("--replace", action="store_true", help="swap this topic's rows, keep everything else")
    a = ap.parse_args()
    run(a.topic, replace=a.replace)
