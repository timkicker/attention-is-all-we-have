"""Mutation score per module from mutmut's .meta files (run from the mutmut work dir, see mutate.sh).

score = killed / (killed + survived + no tests + other), other = timeout or suspicious. Mutants marked equivalent in
EQUIVALENT_FILE are left out of the score and listed apart. Exits 0; it reports, it does not judge."""

import json
import sys
from collections import Counter
from pathlib import Path

from mutmut.stats import status_by_exit_code

EQUIVALENT_FILE = Path(__file__).resolve().parent / "mutate_equivalent.txt"


def equivalent() -> dict[str, str]:
    out = {}
    if EQUIVALENT_FILE.is_file():
        for line in EQUIVALENT_FILE.read_text().splitlines():
            if line.strip() and not line.startswith("#"):
                name, _, why = line.partition(" ")
                out[name] = why.strip()
    return out


def main() -> int:
    eq = equivalent()
    rows, survivors = [], []
    for meta in sorted(Path("mutants").rglob("*.py.meta")):
        module = str(meta.relative_to("mutants")).removesuffix(".meta")
        codes = json.loads(meta.read_text())["exit_code_by_key"]
        c = Counter()
        for name, code in codes.items():
            status = status_by_exit_code[code]
            if status == "survived" and name in eq:
                status = "equivalent"
            c[status] += 1
            if status in ("survived", "no tests", "timeout", "suspicious"):
                survivors.append((status, name))
        counted = sum(v for k, v in c.items() if k not in ("equivalent", "not checked", "skipped"))
        score = 100 * c["killed"] / counted if counted else 0.0
        other = counted - c["killed"] - c["survived"] - c["no tests"]
        rows.append((module, len(codes), c["killed"], c["survived"], c["no tests"], other, c["equivalent"],
                     c["not checked"], score))
    head = ("mutants", "killed", "survived", "no test", "other", "equiv", "pending")
    print(f"{'module':32}" + "".join(f"{h:>9}" for h in head) + f"{'score':>8}")
    for m, *nums, sc in rows:
        print(f"{m:32}" + "".join(f"{n:9}" for n in nums) + f"{sc:7.1f}%")
    tot = [sum(r[i] for r in rows) for i in range(1, 8)]
    counted = tot[1] + tot[2] + tot[3] + tot[4]
    print(f"{'total':32}" + "".join(f"{n:9}" for n in tot) + f"{100 * tot[1] / counted if counted else 0:7.1f}%")
    if "-v" in sys.argv:
        for status, name in survivors:
            print(f"{status:10} {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
