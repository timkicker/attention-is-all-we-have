"""Apply SQL files to the Parallax database: `python scripts/load_sql.py [--reset] FILE...`.

Statements are split on a semicolon at the end of a line, which holds for schema.sql and the seeds.
--reset drops every table in the database first. Gzipped files are read directly.
"""

import argparse
import gzip
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from contract.db import connect  # noqa: E402


def statements(path: Path):
    opener = gzip.open if path.suffix == ".gz" else open
    buf = []
    with opener(path, "rt", encoding="utf-8") as f:
        for line in f:
            if not buf and (line.startswith("--") or not line.strip()):
                continue
            buf.append(line)
            if line.rstrip().endswith(";"):
                yield "".join(buf).rstrip().rstrip(";")
                buf = []
    if "".join(buf).strip():
        yield "".join(buf)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("files", nargs="*", type=Path)
    a = ap.parse_args()
    conn = connect()
    with conn.cursor() as c:
        if a.reset:
            c.execute("SET FOREIGN_KEY_CHECKS=0")
            c.execute("SHOW TABLES")
            for (t,) in c.fetchall():
                c.execute(f"DROP TABLE `{t}`")
        for path in a.files:
            n = 0
            for stmt in statements(path):
                c.execute(stmt)
                n += 1
            print(f"{path}: {n} statements")


if __name__ == "__main__":
    main()
