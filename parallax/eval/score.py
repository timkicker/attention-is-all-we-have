"""A10: judge agreement with the human gold set (accuracy, Cohen's kappa, overall and per language) and alignment
recall (R@1, R@5, R@10 of the gold `same` partner among exact nearest neighbours). Writes eval/report.json and the
stat key judge_eval."""

import json
import os
from collections import Counter, defaultdict
from pathlib import Path

LABELS = ("same", "partial", "contradicts", "different")
ROOT = Path(__file__).resolve().parent.parent
GOLD = ROOT / "eval" / "gold.jsonl"
REPORT = ROOT / "eval" / "report.json"


def kappa(pairs: list[tuple[str, str]]) -> float | None:
    """Cohen's kappa for (gold, predicted) label pairs."""
    n = len(pairs)
    if not n:
        return None
    po = sum(g == p for g, p in pairs) / n
    cg = Counter(g for g, _ in pairs)
    cp = Counter(p for _, p in pairs)
    pe = sum(cg[k] * cp[k] for k in set(cg) | set(cp)) / (n * n)
    return round((po - pe) / (1 - pe), 3) if pe < 1 else 1.0


def agreement(pairs: list[tuple[str, str]]) -> dict:
    n = len(pairs)
    return {"pairs": n, "accuracy": round(sum(g == p for g, p in pairs) / n, 3) if n else None, "kappa": kappa(pairs)}


def recall_at(ranks: list[int | None], ks=(1, 5, 10)) -> dict:
    n = len(ranks)
    return {f"R@{k}": round(sum(1 for r in ranks if r is not None and r <= k) / n, 3) if n else None for k in ks}


def judge_report(gold: list[dict], predicted: dict[tuple, str]) -> dict:
    """gold rows {a_lang, a_h, b_lang, b_h, label}; predicted {(a_lang, a_h, b_lang, b_h): label}."""
    allp, by_lang = [], defaultdict(list)
    confusion = Counter()
    for g in gold:
        p = predicted.get((g["a_lang"], g["a_h"], g["b_lang"], g["b_h"]))
        if p is None:
            continue
        allp.append((g["label"], p))
        by_lang[g["b_lang"] if g["a_lang"] == "en" else g["a_lang"]].append((g["label"], p))
        confusion[f"{g['label']}->{p}"] += 1
    return {
        **agreement(allp),
        "per_lang": {k: agreement(v) for k, v in sorted(by_lang.items())},
        "confusion": dict(confusion.most_common()),
    }


def headline(judge: dict[str, dict], default: str) -> dict:
    """The one agreement number the app shows (Check and Under the hood read accuracy, kappa and n at the top of
    stat judge_eval): the prompt version the app judges with, else the best measured one."""
    have = {pv: r for pv, r in judge.items() if r.get("accuracy") is not None}
    if not have:
        return {}
    pv = default if default in have else max(have, key=lambda k: (have[k]["accuracy"], have[k]["pairs"]))
    r = have[pv]
    return {"accuracy": r["accuracy"], "kappa": r["kappa"], "n": r["pairs"], "prompt_version": pv, "model": r["model"]}


def load_gold(path: Path = GOLD) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def judge_missing(cur, gold: list[dict], prompt_version: str) -> int:
    """Judge every gold pair that has no verdict for this prompt version (one candidate per call)."""
    import json as _json

    from contract.engine import Candidate
    from engine import gemini
    from engine.real import GeminiEngine

    eng = GeminiEngine()
    eng.prompt_version = prompt_version
    n = 0
    for g in gold:
        cur.execute(
            "SELECT 1 FROM verdict WHERE a_lang=%s AND a_h=%s AND b_lang=%s AND b_h=%s AND prompt_version=%s",
            (g["a_lang"], g["a_h"], g["b_lang"], g["b_h"], prompt_version),
        )
        if cur.fetchone():
            continue
        try:
            (v,) = eng.judge(g["a_text"], g["a_lang"], [Candidate(g["b_lang"], 0, g["b_h"], g["b_text"])])
        except gemini.GeminiError:
            continue
        cur.execute(
            "INSERT INTO verdict (a_lang, a_h, b_lang, b_h, prompt_version, label, numbers, terms, model, raw, "
            "judged_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL,UTC_TIMESTAMP(6))",
            (
                g["a_lang"],
                g["a_h"],
                g["b_lang"],
                g["b_h"],
                prompt_version,
                v.label,
                _json.dumps(v.numbers, ensure_ascii=False),
                _json.dumps(v.terms, ensure_ascii=False),
                eng.model_id,
            ),
        )
        n += 1
    return n


def main() -> None:
    import argparse

    from contract.db import connect
    from pipeline import stat

    ap = argparse.ArgumentParser()
    ap.add_argument("--judge", nargs="*", default=[], help="prompt versions to run on unjudged gold pairs first")
    a = ap.parse_args()
    gold = load_gold()
    if not gold:
        raise SystemExit("eval/gold.jsonl is empty: run `make label` first")
    cur = connect().cursor()
    for pv in a.judge:
        print(f"{pv}: judged {judge_missing(cur, gold, pv)} gold pairs that had no verdict")
    cur.execute("SELECT DISTINCT prompt_version FROM verdict ORDER BY prompt_version")
    versions = [r[0] for r in cur.fetchall()]
    report = {"gold_pairs": len(gold), "labels": dict(Counter(g["label"] for g in gold)), "judge": {}}
    for pv in versions:
        cur.execute("SELECT a_lang, a_h, b_lang, b_h, label, model FROM verdict WHERE prompt_version=%s", (pv,))
        rows = cur.fetchall()
        pred = {(a, ah, b, bh): lab for a, ah, b, bh, lab, _ in rows}
        rep = judge_report(gold, pred)
        rep["model"] = rows[0][5] if rows else None
        report["judge"][pv] = rep
        print(f"{pv}: pairs={rep['pairs']} accuracy={rep['accuracy']} kappa={rep['kappa']}")
        for lang, r in rep["per_lang"].items():
            print(f"  {lang}: pairs={r['pairs']} accuracy={r['accuracy']} kappa={r['kappa']}")
    # alignment recall: rank of the gold `same` partner among the exact 10 nearest in its edition, today
    ranks = []
    for g in gold:
        if g["label"] != "same":
            continue
        cur.execute(
            "SELECT h FROM claim FOR SYSTEM_TIME ALL IGNORE INDEX(emb) WHERE lang=%s AND topic_id='winterwar' "
            "ORDER BY VEC_DISTANCE_COSINE(emb, (SELECT emb FROM claim FOR SYSTEM_TIME ALL WHERE lang=%s AND h=%s "
            "LIMIT 1)) LIMIT 10",
            (g["b_lang"], g["a_lang"], g["a_h"]),
        )
        hs = []
        for (h,) in cur.fetchall():
            if h not in hs:
                hs.append(h)
        ranks.append(hs.index(g["b_h"]) + 1 if g["b_h"] in hs else None)
    report["alignment"] = {"same_pairs": len(ranks), **recall_at(ranks)}
    print(f"alignment over {len(ranks)} gold same pairs: {report['alignment']}")
    report = {**headline(report["judge"], os.environ.get("JUDGE_PROMPT", "judge-v1")), **report}
    print(f"headline: {report.get('prompt_version')} accuracy={report.get('accuracy')} n={report.get('n')}")
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    stat.put(cur, "judge_eval", report)


if __name__ == "__main__":
    main()
