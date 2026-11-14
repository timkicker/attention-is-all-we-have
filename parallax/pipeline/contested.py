"""A12 step 5: contested claims from the history of claim_life_fi, one SQL statement, no new table."""

import time
from collections import Counter

from contract.db import connect
from pipeline import stat
from pipeline.fetch import ROOT

SQL = "\n".join(
    line
    for line in (ROOT / "pipeline" / "contested.sql").read_text(encoding="utf-8").splitlines()
    if not line.startswith("--")
)


def run() -> dict:
    cur = connect().cursor()
    t = time.perf_counter()
    cur.execute(SQL)
    rows = cur.fetchall()
    ms = round((time.perf_counter() - t) * 1000, 1)
    pages = Counter(r[1] for r in rows)
    top = [
        {"page_id": r[0], "title": r[1], "h": r[2], "lives": int(r[3]), "alive_now": int(r[4] or 0), "text": r[5][:300]}
        for r in rows[:20]
    ]
    out = {
        "total": len(rows),
        "pages": len(pages),
        "max_lives": int(rows[0][3]) if rows else 0,
        "query_ms": ms,
        "top_pages": pages.most_common(20),
        "top": top,
        "talvisota": [{"lives": int(r[3]), "text": r[5][:300]} for r in rows if r[0] == 1256],
    }
    stat.put(cur, "contested_claims", out)
    print(f"contested claims (>= 3 lives): {len(rows)} in {len(pages)} articles, query {ms} ms")
    for x in top:
        assert x["lives"] >= 3
        print(f"  {x['lives']:3} {x['title'][:40]:40} {x['text'][:90]}")
    print("Talvisota:")
    for x in out["talvisota"][:10]:
        print(f"  {x['lives']:3} {x['text'][:110]}")
    return out


if __name__ == "__main__":
    run()
