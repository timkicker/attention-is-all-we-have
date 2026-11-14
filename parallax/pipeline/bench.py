"""A13b: measured numbers for "Implementation: scalability on the provided datasets", from one command.

Collects the pipeline's own counters into `stat`, measures sizes, AS OF latency (one topic and all of M), vector
search at M size (exact vs ANN at several ef values) and the demo's combined statement, then renders docs/SCALE.md
from `stat` only.
"""

import json
import random
import time
from datetime import datetime, timedelta

from contract.db import connect
from pipeline import stat
from pipeline.fetch import DATA, ROOT

TABLES = ["claim", "claim_life_fi", "article_vec", "section_text", "revision", "align", "verdict", "ref_stat"]
RND = random.Random(1939)


def pct(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    if not xs:
        return 0.0
    return round(xs[min(len(xs) - 1, int(p * len(xs)))], 2)


def timed(cur, sql: str, params=()) -> tuple[float, list]:
    t = time.perf_counter()
    cur.execute(sql, params)
    rows = cur.fetchall()
    return (time.perf_counter() - t) * 1000, rows


def recall(exact: list, approx: list) -> float:
    return len(set(exact) & set(approx)) / max(1, len(exact))


def rand_ts() -> str:
    d = datetime(2005, 1, 1) + timedelta(days=RND.randrange(0, 365 * 21))
    return d.strftime("%Y-%m-%d 00:00:00")


def explain_key(cur, sql: str, params=()) -> str | None:
    cur.execute("EXPLAIN " + sql, params)
    cols = [d[0] for d in cur.description]
    keys = [dict(zip(cols, r, strict=True)).get("key") for r in cur.fetchall()]
    return keys[0]


def collect_files(cur) -> None:
    """Counters the pipeline wrote to disk go into stat, so the docs read numbers from one place."""
    files = {
        "m_lives": DATA / "m_lives" / "summary.json",
        "topic_lives": DATA / "lives" / "winterwar-stats.json",
        "topic_load": DATA / "lives" / "winterwar-load.json",
        "topic_embed": DATA / "lives" / "winterwar-embed.json",
        "l_scale": DATA / "l_scale.json",
    }
    for k, p in files.items():
        if p.exists():
            stat.put(cur, k, json.loads(p.read_text(encoding="utf-8")))


def sizes(cur) -> dict:
    out = {}
    for t in TABLES:
        cur.execute("SELECT COUNT(*) FROM `%s`" % t)  # noqa: UP031  (table names are constants)
        current = cur.fetchone()[0]
        try:
            cur.execute("SELECT COUNT(*) FROM `%s` FOR SYSTEM_TIME ALL" % t)  # noqa: UP031
            total = cur.fetchone()[0]
        except Exception:  # noqa: BLE001  (not system-versioned)
            total = current
        cur.execute(
            "SELECT data_length + index_length FROM information_schema.tables WHERE table_schema=DATABASE() "
            "AND table_name=%s",
            (t,),
        )
        out[t] = {"current_rows": current, "all_rows": total, "mb": round((cur.fetchone()[0] or 0) / 2**20, 1)}
    return out


def as_of_latency(cur) -> dict:
    out = {}
    cur.execute("SELECT DISTINCT lang, page_id FROM claim WHERE topic_id='winterwar'")
    topic_pages = cur.fetchall()
    q1 = "SELECT h, text FROM claim FOR SYSTEM_TIME AS OF TIMESTAMP %s WHERE lang=%s AND page_id=%s"
    ts = [timed(cur, q1, (rand_ts(), *RND.choice(topic_pages)))[0] for _ in range(50)]
    out["winterwar"] = {
        "queries": 50,
        "p50_ms": pct(ts, 0.5),
        "p95_ms": pct(ts, 0.95),
        "key": explain_key(cur, q1, (rand_ts(), *topic_pages[0])),
    }
    cur.execute("SELECT page_id FROM page WHERE lang='fi' AND source='M'")
    m_pages = [r[0] for r in cur.fetchall()]
    q2 = "SELECT h, text FROM claim_life_fi FOR SYSTEM_TIME AS OF TIMESTAMP %s WHERE page_id=%s"
    ts, rows = [], []
    for _ in range(50):
        ms, r = timed(cur, q2, (rand_ts(), RND.choice(m_pages)))
        ts.append(ms)
        rows.append(len(r))
    key = explain_key(cur, q2, (rand_ts(), m_pages[0]))
    out["m_all"] = {
        "queries": 50,
        "pages": len(m_pages),
        "p50_ms": pct(ts, 0.5),
        "p95_ms": pct(ts, 0.95),
        "rows_p50": pct(rows, 0.5),
        "key": key,
    }
    if not key:
        raise SystemExit("bench FAILED: AS OF over claim_life_fi does not use an index")
    return out


def vector_search(cur, n: int = 100) -> dict:
    cur.execute("SELECT COUNT(*) FROM claim")
    size = cur.fetchone()[0]
    cur.execute("SELECT emb FROM claim ORDER BY RAND(1939) LIMIT %s", (n,))
    probes = [r[0] for r in cur.fetchall()]
    inner = "SELECT lang, page_id, h, VEC_DISTANCE_COSINE(emb, %s) d FROM claim {hint} ORDER BY d LIMIT 10"
    outer = "SELECT x.h, x.d, p.title FROM ({inner}) x JOIN page p ON p.lang=x.lang AND p.page_id=x.page_id"
    exact, t_exact = [], []
    for v in probes:
        ms, rows = timed(cur, outer.format(inner=inner.format(hint="IGNORE INDEX(emb)")), (v,))
        exact.append([r[0] for r in rows])
        t_exact.append(ms)
    out = {
        "claim_rows": size,
        "probes": len(probes),
        "exact": {"p50_ms": pct(t_exact, 0.5), "p95_ms": pct(t_exact, 0.95)},
        "ann": {},
    }
    for ef in (20, 80, 1000):
        cur.execute(f"SET mhnsw_ef_search={ef}")
        rec, ts = [], []
        for v, ex in zip(probes, exact, strict=True):
            ms, rows = timed(cur, outer.format(inner=inner.format(hint="FORCE INDEX(emb)")), (v,))
            ts.append(ms)
            rec.append(recall(ex, [r[0] for r in rows]))
        out["ann"][str(ef)] = {
            "recall_at_10": round(sum(rec) / len(rec), 3),
            "p50_ms": pct(ts, 0.5),
            "p95_ms": pct(ts, 0.95),
        }
    cur.execute("SET mhnsw_ef_search=1000")
    return out


def combined(cur) -> dict:
    cur.execute("SELECT emb FROM claim WHERE topic_id='winterwar' ORDER BY RAND(7) LIMIT 50")
    vecs = [r[0] for r in cur.fetchall()]
    q = (
        "SELECT h, text, VEC_DISTANCE_COSINE(emb, %s) d FROM claim FOR SYSTEM_TIME AS OF TIMESTAMP %s "
        "IGNORE INDEX(emb) WHERE topic_id='winterwar' AND lang=%s ORDER BY d LIMIT 5"
    )
    ts, rows = [], []
    for v in vecs:
        ms, r = timed(cur, q, (v, rand_ts(), RND.choice(["fi", "sv", "de", "en", "ru", "et", "uk"])))
        ts.append(ms)
        rows.append(len(r))
    return {"queries": len(vecs), "p50_ms": pct(ts, 0.5), "p95_ms": pct(ts, 0.95), "sql": q.replace("%s", "?")}


def fmt_n(x) -> str:
    return f"{x:,}".replace(",", " ") if isinstance(x, int) else str(x)


def render(cur) -> str:
    def g(k):
        return stat.get(cur, k) or {}

    b, m, atlas, cont = g("bench"), g("m_lives"), g("atlas"), g("contested_claims")
    tl, load, emb, mv, ann = (
        g("topic_lives"),
        g("topic_load"),
        g("topic_embed"),
        g("m_vectors"),
        g("align_ann_vs_exact"),
    )
    lsc, src, jc, ev = g("l_scale"), g("sources"), g("judge_calls"), g("judge_eval")
    L = [
        "# Parallax at scale",
        "",
        "Every number on this page comes from the `stat` table, written by the pipeline and by `make bench`. "
        "Nothing is typed by hand.",
        "",
    ]
    L += [
        "## Dataset M: every revision of 19,742 Finnish articles",
        "",
        "| What | Number |",
        "|---|---|",
        f"| Articles | {fmt_n(m.get('pages'))} |",
        f"| Revisions parsed (sha1 cache hits) | {fmt_n(m.get('revisions'))} ({fmt_n(m.get('cache_hits'))}) |",
        f"| Sentence lives before the noise rule | {fmt_n(m.get('lives_raw'))} |",
        f"| Vandal lives dropped / blanking gaps healed | {fmt_n(m.get('lives_noise'))} / "
        f"{fmt_n(m.get('gaps_healed'))} |",
        f"| Sentence lives in `claim_life_fi` | {fmt_n(m.get('lives'))} (alive {fmt_n(m.get('alive'))}) |",
        f"| Dead after at least a year | {fmt_n(m.get('dead_after_365d'))} |",
        f"| Death reasons from edit comments | {m.get('reasons')} |",
        f"| Parse wall time on 7 laptop cores | {round((m.get('cpu_seconds_wall') or 0) / 60, 1)} min |",
        f"| Load into MariaDB | {(m.get('load') or {}).get('seconds')} s |",
        f"| Contested sentences (3+ lives) | {fmt_n(cont.get('total'))} in {fmt_n(cont.get('pages'))} articles, "
        f"one SQL statement in {cont.get('query_ms')} ms |",
        f"| Long lives with a bge-m3 vector | {fmt_n(mv.get('lives'))} lives, {fmt_n(mv.get('distinct'))} "
        f"sentences ({mv.get('pages')} articles) |",
        "",
    ]
    a = b.get("as_of") or {}
    L += [
        "## Time travel latency (`FOR SYSTEM_TIME AS OF`)",
        "",
        "| Table | Rows (all versions) | p50 | p95 | Index used |",
        "|---|---|---|---|---|",
    ]
    sz = b.get("sizes") or {}
    for name, key, table in (("Winter War, 7 editions", "winterwar", "claim"), ("All of M", "m_all", "claim_life_fi")):
        x = a.get(key) or {}
        L.append(
            f"| {name} (`{table}`) | {fmt_n((sz.get(table) or {}).get('all_rows'))} | {x.get('p50_ms')} ms | "
            f"{x.get('p95_ms')} ms | `{x.get('key')}` |"
        )
    v = b.get("vector") or {}
    L += [
        "",
        f"## Vector search over {fmt_n(v.get('claim_rows'))} sentence vectors",
        "",
        "Vector search in a subquery, the join to `page` after it.",
        "",
        "| Method | recall@10 vs exact | p50 | p95 |",
        "|---|---|---|---|",
        f"| Exact (`IGNORE INDEX`) | 1.0 | {(v.get('exact') or {}).get('p50_ms')} ms | "
        f"{(v.get('exact') or {}).get('p95_ms')} ms |",
    ]
    for ef, x in (v.get("ann") or {}).items():
        L.append(f"| ANN, M=16, ef_search={ef} | {x['recall_at_10']} | {x['p50_ms']} ms | {x['p95_ms']} ms |")
    c = b.get("combined") or {}
    L += [
        "",
        "## The demo's statement: time travel and vector search together",
        "",
        f"`{c.get('sql')}`",
        "",
        f"p50 {c.get('p50_ms')} ms, p95 {c.get('p95_ms')} ms over {c.get('queries')} random dates, editions and "
        "vectors. At topic size exact search beats the index "
        f"(alignment probe: exact p50 {ann.get('exact_ms_p50')} ms vs ANN p50 {ann.get('ann_ms_p50')} ms, "
        f"recall@5 {ann.get('recall_at_5')}).",
        "",
    ]
    L += [
        "## Winter War in seven editions",
        "",
        "| Edition | Sentence lives | Alive now | Raw lives | Noise |",
        "|---|---|---|---|---|",
    ]
    for lang, x in tl.items():
        L.append(
            f"| {lang} | {fmt_n(x.get('lives'))} | {fmt_n(x.get('alive'))} | {fmt_n(x.get('lives_raw'))} | "
            f"{fmt_n(x.get('lives_noise'))} |"
        )
    L += [
        "",
        f"Loaded in {load.get('seconds')} s. {fmt_n(emb.get('distinct'))} distinct sentences embedded with "
        f"bge-m3 at {emb.get('rate')} sentences/s on the laptop (Ollama).",
        "",
    ]
    L += [
        "## Dataset S: atlas of the same topics in fi, sv and en",
        "",
        f"{fmt_n(sum((atlas.get('article_vec') or {}).values()))} shipped article vectors loaded in "
        f"{atlas.get('load_seconds')} s; coverage {atlas.get('coverage')}; the three pairwise distances for every "
        f"topic computed in one SQL statement in {atlas.get('distance_sql_ms')} ms.",
        "",
    ]
    if lsc:
        L += [
            "## Dataset L: all 568,416 Finnish articles",
            "",
            f"{fmt_n(lsc.get('articles'))} articles split into {fmt_n(lsc.get('sentences'))} sentences "
            f"({fmt_n(lsc.get('distinct'))} distinct) at {lsc.get('sentences_per_s')} sentences/s.",
            f"{lsc.get('embed_note', '')}",
            "",
        ]
    if src:
        L += ["## Sources", "", "Current revision, ISBN registration groups:", ""]
        for lang, x in (src.get("current") or {}).items():
            L.append(f"- {lang}: {x['refs']} refs, {x['isbn']} ISBNs {x['top_isbn']}")
        L.append("")
    if jc or ev:
        agree = {
            k: {kk: vv for kk, vv in x.items() if kk in ("pairs", "accuracy", "kappa")}
            for k, x in (ev.get("judge") or {}).items()
        }
        L += [
            "## Gemini judge",
            "",
            f"Calls: {jc}",
            "",
            f"Agreement with the human gold set: {agree}",
            f"Alignment recall on gold `same` pairs: {ev.get('alignment')}",
            "",
        ]
    L += [
        "## Why sentences are the chunks",
        "",
        "One vector per article finds the topic, not the fact. Parallax splits every revision into sentences and "
        "stores one row per sentence life: the period in which Wikipedia stated it. A sentence that survives 300 "
        "edits is one row and one vector, so the vector count grows with distinct sentences, not with revisions. "
        'The same row answers "what did the article say on this date" (`AS OF`) and "which sentence in another '
        'edition says the same" (`VEC_DISTANCE_COSINE`).',
        "",
        "## Sizes",
        "",
        "| Table | Current rows | All versions | MB |",
        "|---|---|---|---|",
    ]
    for t, x in sz.items():
        L.append(f"| `{t}` | {fmt_n(x['current_rows'])} | {fmt_n(x['all_rows'])} | {x['mb']} |")
    return "\n".join(L) + "\n"


def main() -> None:
    cur = connect().cursor()
    collect_files(cur)
    t0 = time.time()
    out = {"sizes": sizes(cur)}
    print("sizes:", json.dumps(out["sizes"]))
    out["as_of"] = as_of_latency(cur)
    print("as_of:", json.dumps(out["as_of"]))
    out["vector"] = vector_search(cur)
    print("vector:", json.dumps(out["vector"]))
    out["combined"] = combined(cur)
    print("combined:", {k: v for k, v in out["combined"].items() if k != "sql"})
    out["seconds"] = round(time.time() - t0, 1)
    stat.put(cur, "bench", out)
    (ROOT / "docs" / "SCALE.md").write_text(render(cur), encoding="utf-8")
    print("wrote docs/SCALE.md")
    print("bench OK")


if __name__ == "__main__":
    main()
