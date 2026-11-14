"""A12 step 4: vectors for the long-lived Finnish lives of M, loaded into claim with topic_id NULL.

Subset: lives that are alive or lived at least 365 days. Without a GPU (EMBED_BACKEND=ollama) only the
--pages articles with the most `unsourced` or `error` deaths are taken; with Verda (remote/st) use --all.
"""

import argparse
import time

import numpy as np

from contract.db import connect
from engine.embed import VectorStore, embed_texts
from pipeline import stat
from pipeline.load import batches

LONG_LIVES = "(died_rev IS NULL OR TIMESTAMPDIFF(DAY, row_start, row_end) >= 365)"


def pick_pages(cur, n: int) -> list[int]:
    cur.execute(
        "SELECT page_id FROM claim_life_fi FOR SYSTEM_TIME ALL WHERE reason IN ('unsourced','error') "
        "AND page_id NOT IN (SELECT page_id FROM page WHERE topic_id IS NOT NULL AND lang='fi') "
        "GROUP BY page_id ORDER BY COUNT(*) DESC, page_id LIMIT %s",
        (n,),
    )
    return [r[0] for r in cur.fetchall()]


def run(n_pages: int | None) -> None:
    conn = connect()
    cur = conn.cursor()
    where = LONG_LIVES + " AND page_id NOT IN (SELECT page_id FROM page WHERE topic_id IS NOT NULL AND lang='fi')"
    params: tuple = ()
    pages = None
    if n_pages:
        pages = pick_pages(cur, n_pages)
        where += f" AND page_id IN ({', '.join(['%s'] * len(pages))})"
        params = tuple(pages)
    cur.execute(
        "SELECT page_id, h, text, born_rev, died_rev, died_comment, has_ref, had_ref, row_start, row_end "
        f"FROM claim_life_fi FOR SYSTEM_TIME ALL WHERE {where}",
        params,
    )
    lives = cur.fetchall()
    texts = {}
    for lv in lives:
        texts.setdefault(lv[1], lv[2])
    store = VectorStore()
    todo = [t for h, t in texts.items() if h not in store]
    print(
        f"pages={len(pages) if pages else 'all'} lives={len(lives)} distinct={len(texts)} to_embed={len(todo)}",
        flush=True,
    )
    t0 = time.time()
    last = [t0]

    def progress(done, total):
        if time.time() - last[0] > 60 or done == total:
            last[0] = time.time()
            print(f"  embedded {done}/{total} {done / (time.time() - t0):.1f}/s", flush=True)

    embed_texts(todo, store, progress=progress)
    secs = time.time() - t0
    conn.autocommit(False)
    cur.execute("SET system_versioning_insert_history=1")
    # DELETE on a system-versioned table only moves rows into history, so a reload needs `make load` first.
    cur.execute("SELECT COUNT(*) FROM claim FOR SYSTEM_TIME ALL WHERE lang='fi' AND topic_id IS NULL")
    if cur.fetchone()[0]:
        raise SystemExit("claim already has M rows; run `make load` (schema reset) before loading them again")
    cols = (
        "lang, page_id, h, topic_id, section, text, born_rev, died_rev, died_comment, time_precision, "
        "has_ref, had_ref, emb, row_start"
    )
    hist = [lv for lv in lives if lv[4] is not None]  # died_rev set: a history row
    now = [lv for lv in lives if lv[4] is None]
    n = 0
    for rows, with_end in ((hist, True), (now, False)):
        sql = (
            f"INSERT INTO claim ({cols}{', row_end' if with_end else ''}) VALUES "
            f"({', '.join(['%s'] * (15 if with_end else 14))})"
        )
        data = (
            ("fi", p, h, None, "", text, b, d, dc, "exact", hr, hd, np.asarray(store.get(h), dtype="<f4").tobytes(), rs)
            + ((re_,) if with_end else ())
            for p, h, text, b, d, dc, hr, hd, rs, re_ in rows
        )
        for chunk in batches(data):
            cur.executemany(sql, chunk)
            n += len(chunk)
        conn.commit()
    conn.autocommit(True)
    out = {
        "pages": len(pages) if pages else "all",
        "lives": len(lives),
        "distinct": len(texts),
        "embedded_now": len(todo),
        "seconds": round(secs, 1),
        "rate": round(len(todo) / secs, 2) if todo and secs else None,
        "claim_rows": n,
    }
    stat.put(cur, "m_vectors", out)
    print(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=100)
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    run(None if a.all else a.pages)
