"""A9: English machine-translation glosses for every non-en claim alive today and every demo claim."""

import argparse
import re

import yaml

from contract.db import connect
from engine import gemini
from pipeline import stat
from pipeline.fetch import ROOT


def todo(cur, topic_id: str) -> dict[str, list[tuple[str, str]]]:
    claims = yaml.safe_load((ROOT / "pipeline" / "demo_claims.yaml").read_text(encoding="utf-8"))
    demo = {}
    for c in claims:
        demo.setdefault(c["lang"], []).append(re.compile(c["regex"]))
    cur.execute(
        "SELECT DISTINCT c.lang, c.h, c.text, c.row_end > UTC_TIMESTAMP(6) FROM claim FOR SYSTEM_TIME ALL c "
        "LEFT JOIN gloss g ON g.lang=c.lang AND g.h=c.h "
        "WHERE c.topic_id=%s AND c.lang<>'en' AND g.h IS NULL",
        (topic_id,),
    )
    out: dict[str, dict[str, str]] = {}
    for lang, h, text, alive in cur.fetchall():
        if alive or any(rx.search(text) for rx in demo.get(lang, [])):
            out.setdefault(lang, {})[h] = text
    return {lang: list(d.items()) for lang, d in out.items()}


def run(topic_id: str) -> None:
    from engine.real import GeminiEngine

    eng = GeminiEngine()
    cur = connect().cursor()
    work = todo(cur, topic_id)
    total = sum(len(v) for v in work.values())
    print(f"to gloss: {total} sentences in {len(work)} editions", flush=True)
    n = 0
    for lang, items in work.items():
        for i in range(0, len(items), 20):
            chunk = items[i : i + 20]
            try:
                out = eng.gloss([t for _, t in chunk], lang)
            except gemini.GeminiError:
                continue
            cur.executemany(
                "INSERT INTO gloss (lang, h, text_en, model) VALUES (%s,%s,%s,%s) "
                "ON DUPLICATE KEY UPDATE text_en=VALUES(text_en), model=VALUES(model)",
                [(lang, h, g, eng.model_id) for (h, _), g in zip(chunk, out, strict=True)],
            )
            n += len(chunk)
        print(f"  {lang}: {len(items)} {gemini.stats_line()}", flush=True)
    cur.execute(
        "SELECT COUNT(*) FROM claim c LEFT JOIN gloss g ON g.lang=c.lang AND g.h=c.h "
        "WHERE c.topic_id=%s AND c.lang<>'en' AND g.h IS NULL",
        (topic_id,),
    )
    missing = cur.fetchone()[0]
    stat.put(cur, "gloss", {"glossed": n, "current_without_gloss": missing, "model": eng.model_id})
    print(f"glossed={n} current non-en claims without gloss={missing}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", default="winterwar")
    run(ap.parse_args().topic)
