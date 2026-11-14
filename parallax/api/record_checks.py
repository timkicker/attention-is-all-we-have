"""Record checks of AI answers once, so the Check view works offline: make record-checks.

Input: a JSON list of {question, model, date, answer} (contract/fixtures/answers.json, from A15).
Each answer is checked with the engine in ENGINE (real after M2) and stored with source='recorded'.
Its run_id is a hash of model, question and answer, so recording again replaces the old run.
--fixture records the example answer of the fake engine fixtures instead, for local demos and tests.
"""

import argparse
import json
import sys
from pathlib import Path

from api import checker, sqllog
from contract.db import load_env
from contract.engine import FIXTURES

FIXTURE_MODEL = "example answer (test fixture)"


def fixture_answers() -> list[dict]:
    split = json.loads((FIXTURES / "split.json").read_text(encoding="utf-8"))
    return [
        {
            "question": "What happened at Mainila in November 1939?",
            "model": FIXTURE_MODEL,
            "date": None,
            "answer": v["text"],
        }
        for v in split.values()
    ]


def record(answer: dict) -> str:
    run_id = checker.recorded_run_id(answer.get("model"), answer.get("question"), answer["answer"])
    sqllog.run("DELETE FROM check_claim WHERE run_id = %s", (run_id,))
    sqllog.run("DELETE FROM check_run WHERE run_id = %s", (run_id,))
    return checker.run_check(
        answer["answer"],
        source="recorded",
        answer_model=answer.get("model"),
        answer_date=answer.get("date"),
        question=answer.get("question"),
        run_id=run_id,
    )


def main() -> int:
    load_env()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("path", nargs="?", default="contract/fixtures/answers.json")
    ap.add_argument("--fixture", action="store_true", help="record the fake engine's example answer")
    args = ap.parse_args()
    if args.fixture:
        answers = fixture_answers()
    else:
        path = Path(args.path)
        if not path.exists():
            print(f"{path} does not exist yet (A15 delivers it); use --fixture for the example answer", file=sys.stderr)
            return 1
        answers = json.loads(path.read_text(encoding="utf-8"))
    for a in answers:
        run_id = record(a)
        run = checker.load_run(run_id)
        labels = [x["label"] for c in run["claims"] for x in c["per_lang"].values()]
        print(
            f"{run_id} {a.get('model')}: {len(run['claims'])} claims, "
            + ", ".join(f"{k} {labels.count(k)}" for k in ("says", "stopped_saying", "contradicts", "not_found"))
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
