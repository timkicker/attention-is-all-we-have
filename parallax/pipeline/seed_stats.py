"""A11: the numbers the scale line and the docs read, written to `stat` before a seed dump.

`--app-keys` only (re)writes the keys in the shapes the app reads, on a restored seed: embed_rate with per_s and gpu
(Under the hood) and fi_lives, fi_dead, fi_dead_1y, fi_revisions (the Finnish scale line in Dropped). Without
fi_revisions in stat the API counts table revision, which holds only the Winter War revisions, not all of M."""

import argparse
import json

from contract.db import connect
from pipeline import stat
from pipeline.fetch import DATA

FI_SQL = (
    "SELECT COUNT(*), COALESCE(SUM(row_end < NOW()), 0), "
    "COALESCE(SUM(row_end < NOW() AND DATEDIFF(row_end, row_start) >= 365), 0) FROM claim_life_fi FOR SYSTEM_TIME ALL"
)


def app_values(embed_rate: dict | None, verda: dict | None, m_lives: dict | None, fi: tuple) -> dict:
    """embed_rate keeps its per-machine keys and gains per_s and gpu; fi_* counts come from claim_life_fi (the same
    counts as api/queries/dropped_scale.sql), fi_revisions from the M run."""
    rate = dict(embed_rate or {})
    if verda and rate.get("verda_a100"):
        rate.update(per_s=rate["verda_a100"], gpu=f"{verda['gpu']} on Verda, bge-m3 fp16")
    elif rate.get("laptop_ollama"):
        rate.update(per_s=rate["laptop_ollama"], gpu=None)
    out = {"embed_rate": rate}
    if m_lives and fi[0]:
        out |= {
            "fi_lives": int(fi[0]),
            "fi_dead": int(fi[1]),
            "fi_dead_1y": int(fi[2]),
            "fi_revisions": m_lives["revisions"],
        }
    return out


def app_keys(cur) -> dict:
    cur.execute(FI_SQL)
    vals = app_values(stat.get(cur, "embed_rate"), stat.get(cur, "verda"), stat.get(cur, "m_lives"), cur.fetchone())
    for k, v in vals.items():
        stat.put(cur, k, v)
        print(f"{k}: {v}")
    return vals


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
    app_keys(cur)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--app-keys", action="store_true", help="only the keys in the shapes the app reads")
    if ap.parse_args().app_keys:
        app_keys(connect().cursor())
    else:
        main()
