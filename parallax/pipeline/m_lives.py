"""A12: sentence lives for every revision of the 19,742 Finnish articles in dataset M (the scale layer).

`make m-lives` parses the 16 parquet files with a process pool (sha1 parse cache, noise rule), writes
data/m_lives/versions-NN.jsonl.gz and loads claim_life_fi. The user and anonymous columns are never read.
"""

import argparse
import gzip
import json
import os
import re
import sys
import time
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from datetime import datetime
from pathlib import Path

import pyarrow.parquet as pq

from pipeline.fetch import DATA
from pipeline.lives import walk
from pipeline.parse import ParseCache

M_DIR = DATA / "m"
OUT = DATA / "m_lives"
COLUMNS = ["page_id", "title", "rev_id", "parent_id", "timestamp", "comment", "minor", "sha1", "bytes", "text"]
REASONS = [
    ("unsourced", re.compile(r"lähteetön|lähde puuttuu|ei lähdettä|lähteitä", re.I)),
    ("error", re.compile(r"virhe|väärä|korjaus", re.I)),
    ("speculation", re.compile(r"spekul|huhu|arvailu", re.I)),
]
LONG = 365 * 24 * 3600


def reason(comment: str | None) -> str:
    if not comment or not comment.strip():
        return "none"
    for name, rx in REASONS:
        if rx.search(comment):
            return name
    return "other"


def _ts(v) -> str:
    return v.strftime("%Y-%m-%dT%H:%M:%SZ") if isinstance(v, datetime) else str(v)


def page_lives(page_id: int, title: str, rows: list[dict]) -> dict:
    """Worker: one page's revisions (time order) -> lives with reason, plus counters."""
    cache = ParseCache()
    revs = []
    for r in rows:
        p = cache.get(r["sha1"], r["text"] or "")
        revs.append(
            {"rev_id": r["rev_id"], "ts": r["ts"], "sha1": r["sha1"], "comment": r["comment"], "sentences": p.sentences}
        )
    w = walk(revs, exact=True)
    lives = []
    for lv in w.lives:
        lives.append(
            {
                "page_id": page_id,
                "h": lv["h"],
                "text": lv["text"],
                "born_rev": lv["born_rev"],
                "died_rev": lv["died_rev"],
                "died_comment": lv["died_comment"],
                "reason": reason(lv["died_comment"]) if lv["died_rev"] else "none",
                "has_ref": lv["has_ref"],
                "had_ref": lv["had_ref"],
                "row_start": lv["row_start"],
                "row_end": lv["row_end"],
            }
        )
    return {
        "page_id": page_id,
        "title": title,
        "revisions": len(rows),
        "lives": lives,
        "counts": w.counts | {"parsed": cache.parsed, "cache_hits": cache.cache_hits},
    }


def pages_of(path: Path, only: set[int] | None = None):
    """Yield (page_id, title, rows) per page; pages are contiguous in the M files."""
    f = pq.ParquetFile(path)
    cur_pid, title, rows = None, None, []
    for batch in f.iter_batches(columns=COLUMNS, batch_size=2000):
        cols = batch.to_pydict()
        for i in range(len(cols["page_id"])):
            pid = cols["page_id"][i]
            if pid != cur_pid:
                if cur_pid is not None and rows and (only is None or cur_pid in only):
                    yield cur_pid, title, sorted(rows, key=lambda r: (r["ts"], r["rev_id"]))
                cur_pid, title, rows = pid, cols["title"][i], []
            if only is not None and pid not in only:
                continue
            rows.append(
                {
                    "rev_id": cols["rev_id"][i],
                    "ts": _ts(cols["timestamp"][i]),
                    "sha1": cols["sha1"][i],
                    "comment": cols["comment"][i],
                    "text": cols["text"][i],
                }
            )
    if cur_pid is not None and rows and (only is None or cur_pid in only):
        yield cur_pid, title, sorted(rows, key=lambda r: (r["ts"], r["rev_id"]))


def run_file(path: Path, pool: ProcessPoolExecutor, max_inflight: int, only: set[int] | None = None) -> dict:
    out_path = OUT / f"{path.stem}.jsonl.gz"
    pages_path = OUT / f"{path.stem}.pages.jsonl"
    tot = Counter()
    t0 = time.time()
    inflight = set()
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as f, open(pages_path.with_suffix(".tmp"), "w") as fp:

        def drain(done):
            for fut in done:
                res = fut.result()
                for lv in res["lives"]:
                    f.write(json.dumps(lv, ensure_ascii=False) + "\n")
                fp.write(
                    json.dumps(
                        {"page_id": res["page_id"], "title": res["title"], "revisions": res["revisions"]},
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                tot.update(res["counts"])
                tot["revisions"] += res["revisions"]
                tot["pages"] += 1

        for pid, title, rows in pages_of(path, only):
            inflight.add(pool.submit(page_lives, pid, title, rows))
            if len(inflight) >= max_inflight:
                done, inflight = wait(inflight, return_when=FIRST_COMPLETED)
                drain(done)
        while inflight:
            done, inflight = wait(inflight, return_when=FIRST_COMPLETED)
            drain(done)
    tmp.replace(out_path)
    pages_path.with_suffix(".tmp").replace(pages_path)
    secs = time.time() - t0
    tot["seconds"] = round(secs, 1)
    rate = tot["revisions"] / secs if secs else 0
    hit = tot["cache_hits"] / max(1, tot["cache_hits"] + tot["parsed"])
    print(
        f"{path.name}: pages={tot['pages']} revisions={tot['revisions']} lives={tot['lives']} "
        f"raw={tot['lives_raw']} noise={tot['lives_noise']} healed={tot['gaps_healed']} "
        f"{rate:.0f} rev/s cache_hit={hit:.0%} {secs:.0f}s",
        flush=True,
    )
    (OUT / f"{path.stem}.stats.json").write_text(json.dumps(dict(tot)), encoding="utf-8")
    return dict(tot)


def parse_all(files: list[Path], only: set[int] | None = None) -> None:
    workers = max(1, (os.cpu_count() or 2) - 1)
    t0 = time.time()
    with ProcessPoolExecutor(workers) as pool:
        for i, path in enumerate(files):
            if (OUT / f"{path.stem}.stats.json").exists():
                print(f"{path.name}: done before, skipped", flush=True)
                continue
            run_file(path, pool, max_inflight=workers * 4, only=only)
            if i == 0 and len(files) > 1:
                el = time.time() - t0
                print(f"projection: ~{el * len(files) / 60:.0f} min for {len(files)} files", flush=True)


def summary() -> dict:
    tot = Counter()
    for p in sorted(OUT.glob("versions-*.stats.json")):
        tot.update(json.loads(p.read_text()))
    return dict(tot)


def lives_iter():
    for p in sorted(OUT.glob("versions-*.jsonl.gz")):
        with gzip.open(p, "rt", encoding="utf-8") as f:
            for line in f:
                yield json.loads(line)


def load() -> dict:
    """claim_life_fi (history rows first, then current) and page rows for M."""
    from contract.db import connect
    from pipeline.load import batches

    conn = connect()
    conn.autocommit(False)
    cur = conn.cursor()
    cur.execute("SET system_versioning_insert_history=1")
    cur.execute("SET unique_checks=0")
    cur.execute("SET foreign_key_checks=0")
    t0 = time.time()
    cur.execute("SELECT page_id FROM page WHERE lang='fi'")
    have = {r[0] for r in cur.fetchall()}
    pages = []
    for p in sorted(OUT.glob("versions-*.pages.jsonl")):
        for line in p.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r["page_id"] not in have:
                pages.append(("fi", r["page_id"], None, r["title"][:255], "M", "every"))
    for chunk in batches(pages):
        cur.executemany(
            "INSERT INTO page (lang, page_id, topic_id, title, source, history) VALUES (%s,%s,%s,%s,%s,%s)", chunk
        )
    cols = "page_id, h, text, born_rev, died_rev, died_comment, reason, has_ref, had_ref"
    n = Counter()
    for current in (False, True):
        rows = (
            (
                lv["page_id"],
                lv["h"],
                lv["text"],
                lv["born_rev"],
                lv["died_rev"],
                (lv["died_comment"] or None) and lv["died_comment"][:1000],
                lv["reason"],
                lv["has_ref"],
                lv["had_ref"],
                lv["row_start"],
            )
            + (() if current else (lv["row_end"],))
            for lv in lives_iter()
            if (lv["row_end"] is None) == current
        )
        sql = (
            f"INSERT INTO claim_life_fi ({cols}, row_start{'' if current else ', row_end'}) "
            f"VALUES ({', '.join(['%s'] * (10 if current else 11))})"
        )
        for chunk in batches(rows, max_rows=2000):
            cur.executemany(sql, chunk)
            n["current" if current else "history"] += len(chunk)
            if (n["history"] + n["current"]) % 100_000 < 2000:
                conn.commit()
                print(f"  loaded {n['history'] + n['current']}", file=sys.stderr, flush=True)
        conn.commit()
    secs = round(time.time() - t0, 1)
    out = {"pages": len(pages), "history": n["history"], "current": n["current"], "seconds": secs}
    print(f"claim_life_fi: history={n['history']} current={n['current']} pages+={len(pages)} {secs}s")
    return out


def report(load_stats: dict | None = None) -> dict:
    tot = summary()
    lives = Counter()
    reasons = Counter()
    long_dead = 0
    for lv in lives_iter():
        lives["lives"] += 1
        if lv["died_rev"] is None:
            lives["alive"] += 1
        else:
            lives["dead"] += 1
            reasons[lv["reason"]] += 1
            a = datetime.fromisoformat(lv["row_start"])
            b = datetime.fromisoformat(lv["row_end"])
            if (b - a).total_seconds() >= LONG:
                long_dead += 1
    out = {
        "pages": tot.get("pages"),
        "revisions": tot.get("revisions"),
        "lives": lives["lives"],
        "alive": lives["alive"],
        "dead": lives["dead"],
        "dead_after_365d": long_dead,
        "reasons": dict(reasons),
        "lives_raw": tot.get("lives_raw"),
        "lives_noise": tot.get("lives_noise"),
        "gaps_healed": tot.get("gaps_healed"),
        "reverts": tot.get("reverts"),
        "parsed": tot.get("parsed"),
        "cache_hits": tot.get("cache_hits"),
        "cpu_seconds_wall": tot.get("seconds"),
    }
    if load_stats:
        out["load"] = load_stats
    (OUT / "summary.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    for k, v in out.items():
        print(f"{k}: {v}")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", nargs="*", help="parquet file names, default all 16")
    ap.add_argument("--skip-parse", action="store_true")
    ap.add_argument("--skip-load", action="store_true")
    ap.add_argument("--pages", help="comma separated page ids (testing)")
    a = ap.parse_args()
    files = [M_DIR / f for f in a.files] if a.files else sorted(M_DIR.glob("versions-*.parquet"))
    only = {int(x) for x in a.pages.split(",")} if a.pages else None
    if not a.skip_parse:
        parse_all(files, only)
    ls = None if a.skip_load else load()
    report(ls)
