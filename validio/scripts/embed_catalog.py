"""Product vectors for the local semantic search (validio/matching/semantic.py), from data/catalog.db.

Runs on this machine only: the model (BAAI/bge-small-en-v1.5, about 67 MB) is fetched once into data/models, then
every product's English name and group name is embedded on the CPU into data/embeddings.npz. No product text is
sent anywhere. Needs the optional extra: uv sync --extra semantic (make embed does it).
"""

import argparse
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "backend"))
from validio.config import DATA, embeddings_path, models_dir
from validio.matching import semantic


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", type=Path, default=DATA / "catalog.db")
    ap.add_argument("--out", type=Path, default=embeddings_path())
    ap.add_argument("--models", type=Path, default=models_dir())
    args = ap.parse_args()
    if not args.catalog.is_file():
        print(f"NOTHING WAS READ: {args.catalog} missing, run make data index")
        return 2
    con = sqlite3.connect(f"file:{args.catalog}?mode=ro", uri=True)
    rows = con.execute("select id, coalesce(nullif(name_en, ''), name_fi, ''), coalesce(category, '') "
                       "from product where deleted = 0 order by id").fetchall()
    con.close()
    rows = [r for r in rows if r[1]]
    if not rows:
        print("NOTHING WAS READ: no product with a name")
        return 2
    t = time.monotonic()
    embedder = semantic.FastEmbedder(args.models, local_only=False)  # fetches the model the first time only
    vecs = embedder.embed([semantic.product_text(name, cat) for _, name, cat in rows])
    semantic.save(args.out, [r[0] for r in rows], vecs)
    print(f"embedded {len(rows)} products with {semantic.MODEL} in {time.monotonic() - t:.0f} s into {args.out} "
          f"({args.out.stat().st_size / 1e6:.1f} MB), model in {args.models}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
