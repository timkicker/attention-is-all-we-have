"""`make checks`: run pipeline/checks.sql block by block and diff with pipeline/checks_expected.txt.

`--write` stores the current output as the new expectation (review the diff before committing it).
"""

import argparse
import difflib
import re
import sys

from contract.db import connect
from pipeline.fetch import ROOT

SQL = ROOT / "pipeline" / "checks.sql"
EXPECTED = ROOT / "pipeline" / "checks_expected.txt"


def blocks(text: str):
    name = None
    buf: list[str] = []
    for line in text.splitlines():
        if m := re.match(r"--\s*name:\s*(\S+)", line):
            if name and buf:
                yield name, "\n".join(buf).rstrip().rstrip(";")
            name, buf = m.group(1), []
        elif name and line.strip() and not line.startswith("--"):
            buf.append(line)
    if name and buf:
        yield name, "\n".join(buf).rstrip().rstrip(";")


def run() -> list[str]:
    conn = connect()
    out = []
    with conn.cursor() as c:
        for name, sql in blocks(SQL.read_text(encoding="utf-8")):
            c.execute(sql)
            if name.startswith("explain"):
                cols = [d[0] for d in c.description]
                keys = [dict(zip(cols, r, strict=True)).get("key") for r in c.fetchall()]
                out.append(f"{name}: key={','.join(str(k) for k in keys)}")
                continue
            rows = c.fetchall() if c.description else []
            out.append(f"{name}: " + " | ".join(", ".join(str(v) for v in r) for r in rows))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    got = run()
    if a.write:
        EXPECTED.write_text("\n".join(got) + "\n", encoding="utf-8")
        print("\n".join(got))
        print(f"wrote {EXPECTED.name}")
        return 0
    want = EXPECTED.read_text(encoding="utf-8").splitlines() if EXPECTED.exists() else []
    if got == want:
        print("\n".join(got))
        print("checks OK")
        return 0
    sys.stdout.writelines(difflib.unified_diff([w + "\n" for w in want], [g + "\n" for g in got], "expected", "got"))
    print("checks FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
