"""A10: candidate pairs for the human gold set, written to data/gold_candidates.jsonl.

The six spike anchors in en with their nearest partner today in every other edition, plus 12 random judged pairs
per judge label, capped at 60 pairs. The judge's label is kept out of the labelling screen.
"""

import json
import random

from contract.db import connect
from pipeline.fetch import DATA

ANCHORS = {
    "start": "^It began with a Soviet invasion of Finland on 30 November 1939",
    "league": "^The League of Nations deemed the attack illegal",
    "peace": "^Hostilities ceased in March 1940",
    "mainila": "^On 26 November 1939, an incident was reported",
    "puppet": "^On 1 December 1939, the Soviet Union formed a puppet government",
    "raate": "^The Battle of Raate Road",
}
OUT = DATA / "gold_candidates.jsonl"
CAP = 60


def _text(cur, lang, h):
    cur.execute("SELECT text FROM claim FOR SYSTEM_TIME ALL WHERE lang=%s AND h=%s LIMIT 1", (lang, h))
    r = cur.fetchone()
    return r[0] if r else None


def _gloss(cur, lang, h):
    cur.execute("SELECT text_en FROM gloss WHERE lang=%s AND h=%s", (lang, h))
    r = cur.fetchone()
    return r[0] if r else None


def main() -> None:
    cur = connect().cursor()
    cur.execute("SELECT MAX(as_of) FROM align")
    today = cur.fetchone()[0]
    pairs: dict[tuple, dict] = {}
    for name, rx in ANCHORS.items():
        cur.execute("SELECT h FROM claim WHERE lang='en' AND topic_id='winterwar' AND text REGEXP %s LIMIT 1", (rx,))
        r = cur.fetchone()
        if not r:
            print(f"anchor {name}: not found in en today")
            continue
        cur.execute(
            "SELECT dst_lang, dst_h FROM align WHERE as_of=%s AND src_lang='en' AND src_h=%s AND `rank`=1",
            (today, r[0]),
        )
        for dst_lang, dst_h in cur.fetchall():
            pairs[("en", r[0], dst_lang, dst_h)] = {"source": f"anchor:{name}"}
    rnd = random.Random(14)
    for label in ("same", "partial", "contradicts", "different"):
        cur.execute(
            "SELECT a_lang, a_h, b_lang, b_h FROM verdict WHERE label=%s ORDER BY a_lang, a_h, b_lang, b_h", (label,)
        )
        rows = cur.fetchall()
        for row in rnd.sample(rows, min(12, len(rows))):
            pairs.setdefault(tuple(row), {"source": f"random:{label}"})
    items = list(pairs.items())[:CAP]
    rnd.shuffle(items)
    with OUT.open("w", encoding="utf-8") as f:
        for (a_lang, a_h, b_lang, b_h), meta in items:
            f.write(
                json.dumps(
                    {
                        "a_lang": a_lang,
                        "a_h": a_h,
                        "a_text": _text(cur, a_lang, a_h),
                        "a_gloss": _gloss(cur, a_lang, a_h),
                        "b_lang": b_lang,
                        "b_h": b_h,
                        "b_text": _text(cur, b_lang, b_h),
                        "b_gloss": _gloss(cur, b_lang, b_h),
                        **meta,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    print(f"{len(items)} candidate pairs in {OUT.relative_to(DATA.parent)}")


if __name__ == "__main__":
    main()
