"""A13: breadth across dataset S. article_vec from the shipped bge-m3 vectors, atlas_topic with coverage and the
three pairwise distances computed in SQL (VEC_DISTANCE_COSINE joined on wikidata_id)."""

import time

import numpy as np
import pyarrow.parquet as pq

from contract.db import connect
from pipeline import stat
from pipeline.fetch import DATA
from pipeline.load import batches

S = DATA / "s"
LANGS = ("fi", "sv", "en")

ATLAS_SQL = """
INSERT IGNORE INTO atlas_topic (wikidata_id, title_fi, title_sv, title_en, coverage, dist_fi_sv, dist_fi_en,
                                dist_sv_en, topic_id)
SELECT f.wikidata_id, f.title, s.title, e.title,
       CASE WHEN s.page_id IS NOT NULL AND e.page_id IS NOT NULL THEN 'all'
            WHEN s.page_id IS NOT NULL THEN 'fi+sv' WHEN e.page_id IS NOT NULL THEN 'fi+en' ELSE 'fi' END,
       VEC_DISTANCE_COSINE(f.emb, s.emb), VEC_DISTANCE_COSINE(f.emb, e.emb), VEC_DISTANCE_COSINE(s.emb, e.emb),
       t.topic_id
FROM article_vec f
LEFT JOIN article_vec s ON s.lang = 'sv' AND s.wikidata_id = f.wikidata_id
LEFT JOIN article_vec e ON e.lang = 'en' AND e.wikidata_id = f.wikidata_id
LEFT JOIN topic t ON t.wikidata_id = f.wikidata_id
WHERE f.lang = 'fi' AND f.wikidata_id <> ''
ORDER BY f.wikidata_id, f.page_id
"""


def article_rows(lang: str):
    meta = pq.read_table(S / f"articles-{lang}.parquet", columns=["page_id", "wikidata_id", "title"]).to_pylist()
    by_page = {m["page_id"]: m for m in meta}
    vec = pq.read_table(S / f"vectors-bge-m3-{lang}.parquet", columns=["page_id", "truncated", "embedding"])
    pids = vec.column("page_id").to_pylist()
    trunc = vec.column("truncated").to_pylist()
    embs = vec.column("embedding").combine_chunks().values.to_numpy(zero_copy_only=False).reshape(-1, 1024)
    for pid, tr, emb in zip(pids, trunc, embs, strict=True):
        m = by_page.get(pid)
        if not m:
            continue
        yield (
            lang,
            pid,
            m["wikidata_id"] or "",
            m["title"][:255],
            int(bool(tr)),
            np.asarray(emb, dtype="<f4").tobytes(),
        )


def run() -> dict:
    conn = connect()
    cur = conn.cursor()
    t0 = time.time()
    cur.execute("DELETE FROM atlas_topic")
    cur.execute("DELETE FROM article_vec")
    loaded = {}
    conn.autocommit(False)
    for lang in LANGS:
        n = 0
        for chunk in batches(article_rows(lang)):
            cur.executemany(
                "INSERT INTO article_vec (lang, page_id, wikidata_id, title, truncated, emb) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                chunk,
            )
            n += len(chunk)
        conn.commit()
        loaded[lang] = n
    conn.autocommit(True)
    load_s = round(time.time() - t0, 1)
    t = time.perf_counter()
    cur.execute(ATLAS_SQL)
    sql_ms = round((time.perf_counter() - t) * 1000, 1)
    cur.execute("SELECT coverage, COUNT(*) FROM atlas_topic GROUP BY coverage ORDER BY coverage")
    cov = {k: v for k, v in cur.fetchall()}
    cur.execute(
        "SELECT wikidata_id, title_fi, title_sv, title_en, dist_fi_sv, dist_fi_en FROM atlas_topic "
        "WHERE coverage='all' ORDER BY GREATEST(dist_fi_sv, dist_fi_en) DESC LIMIT 10"
    )
    far = [
        {"wikidata_id": r[0], "fi": r[1], "sv": r[2], "en": r[3], "fi_sv": round(r[4], 3), "fi_en": round(r[5], 3)}
        for r in cur.fetchall()
    ]
    cur.execute("SELECT dist_fi_sv, dist_fi_en, dist_sv_en, topic_id FROM atlas_topic WHERE wikidata_id='Q134949'")
    ww = cur.fetchone()
    cur.execute("SELECT SUM(truncated), COUNT(*) FROM article_vec")
    trunc, total = cur.fetchone()
    out = {
        "article_vec": loaded,
        "load_seconds": load_s,
        "distance_sql_ms": sql_ms,
        "coverage": cov,
        "all": cov.get("all", 0),
        "truncated": int(trunc),
        "vectors": int(total),
        "where_to_look_next": far,
        "winterwar": {"fi_sv": ww[0], "fi_en": ww[1], "sv_en": ww[2], "topic_id": ww[3]} if ww else None,
    }
    stat.put(cur, "atlas", out)
    print(f"article_vec {loaded} in {load_s}s; distances for {sum(cov.values())} topics in {sql_ms} ms")
    print(f"coverage {cov}")
    print(f"all={cov.get('all', 0)}")
    print("largest fi/sv/en distance (where to look next):")
    for x in far:
        print(f"  {x['fi_sv']:.3f} {x['fi_en']:.3f} {x['fi']} / {x['sv']} / {x['en']}")
    print(f"Winter War: {out['winterwar']}")
    return out


if __name__ == "__main__":
    run()
