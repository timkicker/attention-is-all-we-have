"""A11: the numbers the scale line and the docs read, written to `stat` before a seed dump."""

import json

from contract.db import connect
from pipeline import stat
from pipeline.fetch import DATA


def main() -> None:
    cur = connect().cursor()

    def one(sql):
        cur.execute(sql)
        return cur.fetchone()[0]

    lives = json.loads((DATA / "lives" / "winterwar-stats.json").read_text())
    m = json.loads((DATA / "m_lives" / "summary.json").read_text())
    emb = json.loads((DATA / "lives" / "winterwar-embed.json").read_text())
    jc = stat.get(cur, "judge_runs") or {}
    vals = {
        "revisions_total": one("SELECT COUNT(*) FROM revision") + m["revisions"] - 2143,
        # fi of the topic is part of M, so topic lives count without fi
        "lives_total": one("SELECT COUNT(*) FROM claim FOR SYSTEM_TIME ALL WHERE topic_id IS NOT NULL AND lang<>'fi'")
        + one("SELECT COUNT(*) FROM claim_life_fi FOR SYSTEM_TIME ALL"),
        "lives_raw": sum(x["lives_raw"] for lang, x in lives.items() if lang != "fi") + m["lives_raw"],
        "lives_noise": sum(x["lives_noise"] for lang, x in lives.items() if lang != "fi") + m["lives_noise"],
        "gaps_healed": sum(x["gaps_healed"] for lang, x in lives.items() if lang != "fi") + m["gaps_healed"],
        "distinct_texts": one("SELECT COUNT(DISTINCT h) FROM claim FOR SYSTEM_TIME ALL"),
        "vectors": one("SELECT COUNT(*) FROM claim FOR SYSTEM_TIME ALL") + one("SELECT COUNT(*) FROM article_vec"),
        "embed_rate": {"laptop_ollama": emb.get("rate")},
        "judge_calls": sum((x or {}).get("calls", 0) for x in jc.values()),
    }
    vr = DATA / "verda_run.json"
    if vr.exists():
        v = json.loads(vr.read_text())
        stat.put(cur, "verda", v)
        vals["embed_rate"]["verda_a100"] = v["m_long_lives"]["texts_per_s"]
    for k, v in vals.items():
        stat.put(cur, k, v)
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
