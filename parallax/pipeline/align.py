"""A8: cache of the top 5 cross-edition candidates per claim at the anchor dates the UI uses.

Every (date, source edition, destination edition) is one SQL statement: both sides cut with
FOR SYSTEM_TIME AS OF the same instant, exact cosine distance, ROW_NUMBER() keeps the best five.
Then 100 random claims are searched again through the vector index (ANN) to measure recall and time.
"""

import argparse
import random
import statistics
import time
from datetime import UTC, date, datetime

from contract.db import connect
from pipeline import stat
from pipeline.fetch import ROOT, topics

ANCHORS = ["2006-01-01", "2010-01-01", "2014-01-01", "2018-01-01", "2022-01-01"]
SQL = (ROOT / "pipeline" / "align.sql").read_text(encoding="utf-8")
SQL = "\n".join(line for line in SQL.splitlines() if not line.startswith("--"))


def anchor_instants(today: date | None = None) -> list[tuple[str, str]]:
    """(as_of date, AS OF instant) pairs; today is cut at the current time."""
    today = today or datetime.now(UTC).date()
    out = [(d, f"{d} 00:00:00") for d in ANCHORS]
    out.append((today.isoformat(), datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")))
    return out


def ann_vs_exact(cur, topic_id: str, langs: list[str], n: int = 100, seed: int = 7) -> dict:
    cur.execute("SELECT lang, h, emb FROM claim WHERE topic_id=%s", (topic_id,))
    rows = cur.fetchall()
    rnd = random.Random(seed)
    sample = rnd.sample(rows, min(n, len(rows)))
    t_exact, t_ann, overlap, hit1 = [], [], [], 0
    q = "SELECT h FROM claim {hint} WHERE topic_id=%s AND lang=%s ORDER BY VEC_DISTANCE_COSINE(emb, %s) LIMIT 5"
    for lang, _h, emb in sample:
        dst = rnd.choice([x for x in langs if x != lang])
        t = time.perf_counter()
        cur.execute(q.format(hint="IGNORE INDEX(emb)"), (topic_id, dst, emb))
        ex = [r[0] for r in cur.fetchall()]
        t_exact.append((time.perf_counter() - t) * 1000)
        t = time.perf_counter()
        cur.execute(q.format(hint="FORCE INDEX(emb)"), (topic_id, dst, emb))
        an = [r[0] for r in cur.fetchall()]
        t_ann.append((time.perf_counter() - t) * 1000)
        overlap.append(len(set(ex) & set(an)) / max(1, len(ex)))
        hit1 += int(bool(ex) and bool(an) and ex[0] == an[0])

    def pct(xs, p):
        xs = sorted(xs)
        return round(xs[min(len(xs) - 1, int(p * len(xs)))], 2)

    return {
        "queries": len(sample),
        "ef_search": 1000,
        "recall_at_5": round(statistics.mean(overlap), 3),
        "top1_agree": round(hit1 / max(1, len(sample)), 3),
        "exact_ms_p50": pct(t_exact, 0.5),
        "exact_ms_p95": pct(t_exact, 0.95),
        "ann_ms_p50": pct(t_ann, 0.5),
        "ann_ms_p95": pct(t_ann, 0.95),
    }


def run(topic_id: str) -> None:
    langs = topics()[topic_id]["langs"]
    conn = connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM align WHERE src_page IN (SELECT page_id FROM page WHERE topic_id=%s)", (topic_id,))
    total_t = time.time()
    per_date = {}
    for as_of, instant in anchor_instants():
        t = time.time()
        n = 0
        for src in langs:
            for dst in langs:
                if src == dst:
                    continue
                cur.execute(SQL, (as_of, instant, instant, topic_id, src, topic_id, dst))
                n += cur.rowcount
        per_date[as_of] = {"rows": n, "seconds": round(time.time() - t, 1)}
        print(f"{as_of}: rows={n} {time.time() - t:.1f}s", flush=True)
    cur.execute("SELECT COUNT(*), COUNT(DISTINCT as_of, src_lang, src_page, src_h, dst_lang, `rank`) FROM align")
    rows, distinct = cur.fetchone()
    cur.execute("SELECT MIN(`rank`), MAX(`rank`) FROM align")
    rmin, rmax = cur.fetchone()
    comp = ann_vs_exact(cur, topic_id, langs)
    print(f"total rows={rows} distinct={distinct} ranks {rmin}..{rmax} in {time.time() - total_t:.0f}s")
    print("ann vs exact:", comp)
    stat.put(cur, "align_ann_vs_exact", comp)
    stat.put(cur, "align", {"per_date": per_date, "rows": rows, "seconds": round(time.time() - total_t, 1)})
    # probe: today, en "reported" Mainila sentence -> de candidates
    cur.execute(
        "SELECT a.`rank`, LEFT(c.text, 70) FROM align a JOIN claim c ON c.lang=a.dst_lang AND c.h=a.dst_h "
        "JOIN claim s ON s.lang=a.src_lang AND s.h=a.src_h "
        "WHERE a.as_of=(SELECT MAX(as_of) FROM align) AND a.src_lang='en' AND a.dst_lang='de' "
        "AND s.text LIKE 'On 26 November 1939, an incident was reported%%' ORDER BY a.`rank`"
    )
    for rk, text in cur.fetchall():
        print(f"  probe en->de rank {rk}: {text}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", default="winterwar")
    run(ap.parse_args().topic)
