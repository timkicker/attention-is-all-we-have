"""A6: embed every distinct sentence text of a topic's lives once (bge-m3), stored under data/emb/."""

import argparse
import json
import sys
import time

import numpy as np

from engine.embed import VectorStore, embed_texts
from pipeline.fetch import read_jsonl
from pipeline.lives import lives_dir


def topic_texts(topic: str) -> dict[str, str]:
    """h -> text over every lives file of the topic (one text per h)."""
    out: dict[str, str] = {}
    for path in sorted(lives_dir().glob(f"{topic}-*.jsonl.gz")):
        if path.name.endswith(".sections.jsonl.gz"):
            continue
        for lv in read_jsonl(path):
            out.setdefault(lv["h"], lv["text"])
    return out


def main(topic: str) -> None:
    texts = topic_texts(topic)
    store = VectorStore()
    todo = [t for h, t in texts.items() if h not in store]
    t0 = time.time()
    last = [t0]

    def progress(done: int, total: int) -> None:
        if time.time() - last[0] > 15 or done == total:
            last[0] = time.time()
            rate = done / (time.time() - t0)
            print(f"  {done}/{total} {rate:.1f}/s", file=sys.stderr, flush=True)

    embed_texts(todo, store, progress=progress)
    secs = time.time() - t0
    rate = len(todo) / secs if todo and secs else 0.0
    print(f"distinct={len(texts)} embedded={len(todo)} cached={len(texts) - len(todo)} rate={rate:.1f}/s")
    stats_path = lives_dir() / f"{topic}-embed.json"
    prev = json.loads(stats_path.read_text()) if stats_path.exists() else {}
    if todo:
        prev = {"distinct": len(texts), "embedded": len(todo), "seconds": round(secs, 1), "rate": round(rate, 2)}
    else:
        prev["distinct"] = len(texts)
    stats_path.write_text(json.dumps(prev), encoding="utf-8")
    # probe: en "reported" vs de "inszenierte" Mainila sentences
    en = [t for t in texts.values() if "an incident was reported" in t or "staged the shelling of Mainila" in t]
    de = [t for t in texts.values() if "inszenierte" in t and "Mainila" in t]
    if en and de:
        a, b = embed_texts([en[-1], de[-1]], store)
        print(f"probe cos_dist(en Mainila, de inszenierte) = {1 - float(np.dot(a, b)):.3f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", default="winterwar")
    main(ap.parse_args().topic)
