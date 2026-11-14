"""Batch bge-m3 embedding on a GPU host (Verda), without HTTP in between (PLAN A6 / A12 step 4).

  uv run python -m engine.embed_batch IN.jsonl.gz OUT_DIR [--batch 256]

IN holds [h, text] lines. Texts are sorted by length so batches pad little, encoded with sentence-transformers in
fp16 and L2-normalised, and written as npz shards (h, float16 vectors) of 50,000 rows. A progress line with the
rate goes to stdout every shard; stats.json records texts, seconds and texts/s for docs/VERDA.md.
"""

import argparse
import gzip
import json
import time
from pathlib import Path

import numpy as np


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("src", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--shard", type=int, default=50_000)
    a = ap.parse_args()
    import torch
    from sentence_transformers import SentenceTransformer

    with gzip.open(a.src, "rt", encoding="utf-8") as f:
        items = [json.loads(line) for line in f]
    items.sort(key=lambda x: len(x[1]))
    a.out.mkdir(parents=True, exist_ok=True)
    t_load = time.time()
    model = SentenceTransformer("BAAI/bge-m3", device="cuda")
    model.half()
    model.max_seq_length = 512
    load_s = time.time() - t_load
    t0 = time.time()
    done = 0
    for k in range(0, len(items), a.shard):
        chunk = items[k : k + a.shard]
        v = model.encode(
            [t for _, t in chunk],
            batch_size=a.batch,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        np.savez(
            a.out / f"shard-{k // a.shard:05d}.npz",
            h=np.array([h for h, _ in chunk], dtype="U16"),
            v=v.astype(np.float16),
        )
        done += len(chunk)
        el = time.time() - t0
        print(f"{done}/{len(items)} {done / el:.0f} texts/s", flush=True)
    secs = time.time() - t0
    stats = {
        "texts": done,
        "seconds": round(secs, 1),
        "texts_per_s": round(done / secs, 1),
        "model_load_s": round(load_s, 1),
        "gpu": torch.cuda.get_device_name(0),
        "batch": a.batch,
        "dtype": "fp16",
        "max_seq_length": 512,
    }
    (a.out / "stats.json").write_text(json.dumps(stats), encoding="utf-8")
    print(json.dumps(stats))


if __name__ == "__main__":
    main()
