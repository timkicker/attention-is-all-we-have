"""A10: terminal labelling loop for the gold set. Run by a human: `make label LABELLER=<initials>`.

Shows both sentences with their English glosses (machine translation) and asks for the relation. Answers go into
eval/gold.jsonl (committed: hashes, labels and the two Wikipedia sentences, no user data) and the gold_pair table.
Already labelled pairs are skipped, so the loop can be stopped with q and resumed.
"""

import argparse
import json
import textwrap

from contract.db import connect
from eval.score import GOLD, load_gold
from pipeline.fetch import DATA

KEYS = {"s": "same", "p": "partial", "c": "contradicts", "d": "different"}
HELP = (
    "s = same fact | p = partial (overlaps, one says more) | c = contradicts (same subject, incompatible) | "
    "d = different fact | k = skip | q = quit"
)


def show(lang: str, text: str, gloss: str | None) -> None:
    print(f"[{lang}] " + textwrap.fill(text, 110, subsequent_indent="     "))
    if gloss and lang != "en":
        print("     machine translation: " + textwrap.fill(gloss, 90, subsequent_indent="     "))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--labeller", required=True)
    a = ap.parse_args()
    cands = [json.loads(x) for x in (DATA / "gold_candidates.jsonl").read_text(encoding="utf-8").splitlines() if x]
    done = {(g["a_lang"], g["a_h"], g["b_lang"], g["b_h"]) for g in load_gold()}
    todo = [c for c in cands if (c["a_lang"], c["a_h"], c["b_lang"], c["b_h"]) not in done]
    cur = connect().cursor()
    print(HELP)
    for i, c in enumerate(todo, 1):
        print(f"\n--- {i}/{len(todo)} ---")
        show(c["a_lang"], c["a_text"], c.get("a_gloss"))
        show(c["b_lang"], c["b_text"], c.get("b_gloss"))
        while True:
            k = input("label [s/p/c/d/k/q]: ").strip().lower()
            if k in KEYS or k in ("k", "q"):
                break
            print(HELP)
        if k == "q":
            break
        if k == "k":
            continue
        row = {
            "a_lang": c["a_lang"],
            "a_h": c["a_h"],
            "b_lang": c["b_lang"],
            "b_h": c["b_h"],
            "label": KEYS[k],
            "labeller": a.labeller[:16],
            "a_text": c["a_text"],
            "b_text": c["b_text"],
            "source": c.get("source"),
        }
        with GOLD.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        cur.execute(
            "INSERT INTO gold_pair (a_lang, a_h, b_lang, b_h, label, labeller, note) VALUES (%s,%s,%s,%s,%s,%s,%s) "
            "ON DUPLICATE KEY UPDATE label=VALUES(label), labeller=VALUES(labeller)",
            (c["a_lang"], c["a_h"], c["b_lang"], c["b_h"], KEYS[k], a.labeller[:16], (c.get("source") or "")[:255]),
        )
    print(f"\n{len(load_gold())} gold pairs in eval/gold.jsonl")


if __name__ == "__main__":
    main()
