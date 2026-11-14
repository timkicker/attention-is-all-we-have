"""A9: Gemini verdicts for aligned pairs, cached in `verdict` by prompt version (skips pairs already judged).

Scopes, in the order the quota should be spent:
  demo  claims about Mainila or the casualty figures, every anchor date, top 5 per destination edition
  fi    every fi claim alive today (the Compare anchor), top 3 per destination edition
  all   every claim alive today, top 1 per destination edition, all six in one call
One Gemini call per (claim, destination edition) with its candidates, or per claim for `all`.
"""

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from contract.db import connect
from contract.engine import Candidate
from engine import gemini
from pipeline import stat

DEMO_RX = r"Mainil|Майнил|Майніл|casualties|tappiot|kaotus|Потери|Втрати|förluster|Verluste|26 662|25 904|22 830"


def tasks(cur, topic_id: str, scope: str, prompt_version: str) -> list[dict]:
    """[{a_lang, a_h, text, as_of, candidates:[Candidate]}] for pairs not yet judged."""
    if scope == "demo":
        where, top, dates = "s.text REGEXP %s", 5, "a.as_of IS NOT NULL"
        params: tuple = (DEMO_RX,)
    elif scope == "fi":
        where, top, dates = "a.src_lang='fi'", 3, "a.as_of=(SELECT MAX(as_of) FROM align)"
        params = ()
    else:
        where, top, dates = "1", 1, "a.as_of=(SELECT MAX(as_of) FROM align)"
        params = ()
    cur.execute(
        f"""SELECT a.src_lang, a.src_h, s.text, a.dst_lang, a.dst_page, a.dst_h, d.text, a.`rank`
            FROM align a
            JOIN claim FOR SYSTEM_TIME ALL s ON s.lang=a.src_lang AND s.page_id=a.src_page AND s.h=a.src_h
            JOIN claim FOR SYSTEM_TIME ALL d ON d.lang=a.dst_lang AND d.page_id=a.dst_page AND d.h=a.dst_h
            LEFT JOIN verdict v ON v.a_lang=a.src_lang AND v.a_h=a.src_h AND v.b_lang=a.dst_lang AND v.b_h=a.dst_h
                 AND v.prompt_version=%s
            WHERE s.topic_id=%s AND {dates} AND a.`rank` <= {top} AND v.label IS NULL AND {where}
            ORDER BY a.src_lang, a.src_h, a.dst_lang, a.`rank`""",
        (prompt_version, topic_id, *params),
    )
    groups: dict[tuple, dict] = {}
    for a_lang, a_h, a_text, b_lang, b_page, b_h, b_text, _rk in cur.fetchall():
        key = (a_lang, a_h) if scope == "all" else (a_lang, a_h, b_lang)
        g = groups.setdefault(key, {"a_lang": a_lang, "a_h": a_h, "text": a_text, "cands": {}})
        g["cands"].setdefault(b_h, Candidate(b_lang, b_page, b_h, b_text))
    return [{**g, "candidates": list(g.pop("cands").values())} for g in groups.values()]


def run(topic_id: str, scope: str, limit: int | None) -> None:
    from engine.real import GeminiEngine

    eng = GeminiEngine()
    conn = connect()
    cur = conn.cursor()
    todo = tasks(cur, topic_id, scope, eng.prompt_version)
    if limit:
        todo = todo[:limit]
    print(f"scope={scope} calls={len(todo)} pairs={sum(len(t['candidates']) for t in todo)}", flush=True)
    t0 = time.time()
    done = failed = pairs = 0

    def one(t):
        return t, eng.judge(t["text"], t["a_lang"], t["candidates"])

    with ThreadPoolExecutor(gemini.MAX_IN_FLIGHT) as pool:
        futs = [pool.submit(one, t) for t in todo]
        for f in as_completed(futs):
            try:
                t, verdicts = f.result()
            except gemini.GeminiError:
                failed += 1  # stays unjudged: the UI shows "candidate, not judged"
                continue
            rows = [
                (
                    t["a_lang"],
                    t["a_h"],
                    c.lang,
                    v.h,
                    eng.prompt_version,
                    v.label,
                    json.dumps(v.numbers, ensure_ascii=False),
                    json.dumps(v.terms, ensure_ascii=False),
                    eng.model_id,
                    json.dumps({"label": v.label, "numbers": v.numbers, "terms": v.terms}, ensure_ascii=False),
                )
                for c, v in zip(t["candidates"], verdicts, strict=True)
            ]
            cur.executemany(
                "INSERT INTO verdict (a_lang, a_h, b_lang, b_h, prompt_version, label, numbers, terms, model, raw, "
                "judged_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,UTC_TIMESTAMP(6)) "
                "ON DUPLICATE KEY UPDATE label=VALUES(label), numbers=VALUES(numbers), terms=VALUES(terms)",
                rows,
            )
            done += 1
            pairs += len(rows)
            if done % 50 == 0:
                print(f"  {done}/{len(todo)} calls, {gemini.stats_line()}", flush=True)
    minutes = round((time.time() - t0) / 60, 1)
    print(
        f"pairs judged={pairs} calls={gemini.STATS['calls']} 429s={gemini.STATS['r429']} failed={failed} "
        f"minutes={minutes}"
    )
    prev = stat.get(cur, "judge_runs") or {}
    prev[scope] = {
        "pairs": pairs,
        "calls": gemini.STATS["calls"],
        "r429": gemini.STATS["r429"],
        "failed": failed,
        "minutes": minutes,
        "model": eng.model_id,
        "prompt_version": eng.prompt_version,
    }
    stat.put(cur, "judge_runs", prev)
    cur.execute(
        "SELECT v.label, v.terms FROM verdict v JOIN claim a ON a.lang=v.a_lang AND a.h=v.a_h "
        "JOIN claim b ON b.lang=v.b_lang AND b.h=v.b_h WHERE v.a_lang='en' AND v.b_lang='de' "
        "AND a.text LIKE 'On 26 November 1939, an incident was reported%%' AND b.text LIKE '%%inszenierte%%'"
    )
    for label, terms in cur.fetchall():
        print(f"probe en reported vs de inszenierte: {label} terms={terms}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", default="winterwar")
    ap.add_argument("--scope", choices=["demo", "fi", "all"], default="demo")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    run(a.topic, a.scope, a.limit)
