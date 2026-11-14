"""A17 (optional): dataset L, all 568,416 current Finnish articles, as measured numbers instead of a promise.

L text is clean Markdown, so no wikitext parser: paragraphs -> contract split_sentences -> claim_hash. Counts
articles, sentences, distinct hashes and the rate. With a GPU embedding backend (EMBED_BACKEND=remote|st) it also
embeds the distinct sentences of a sample and projects the time for all of L. Nothing is loaded into `claim`.
"""

import argparse
import json
import os
import re
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pyarrow.parquet as pq

from contract.engine import claim_hash, split_sentences
from pipeline.fetch import DATA

L_FILE = DATA / "l" / "articles-fi.parquet"
MD_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
MD_MARK = re.compile(r"(\*\*|__|\*|_|`)")
SKIP_LINE = re.compile(r"^\s*(#|\||>|```|-{3,}|={3,})")
LIST = re.compile(r"^\s*([-*+]|\d+\.)\s+")


def md_sentences(text: str) -> list[str]:
    out = []
    block: list[str] = []

    def flush():
        if block:
            out.extend(split_sentences(" ".join(block)))
            block.clear()

    for line in (text or "").split("\n"):
        if not line.strip() or SKIP_LINE.match(line):
            flush()
            continue
        line = MD_MARK.sub("", MD_LINK.sub(r"\1", line))
        if LIST.match(line):
            flush()
            out.extend(split_sentences(LIST.sub("", line)))
            continue
        block.append(line.strip())
    flush()
    return out


def _row_group(i: int) -> tuple[int, int, np.ndarray, list[str]]:
    t = pq.ParquetFile(L_FILE).read_row_group(i, columns=["text"])
    n_art, hs, sample = 0, [], []
    for text in t.column("text").to_pylist():
        n_art += 1
        for s in md_sentences(text):
            hs.append(int(claim_hash(s), 16))
            if len(sample) < 40:
                sample.append(s)
    return n_art, len(hs), np.array(hs, dtype=np.uint64), sample


def run(sample_articles: int) -> dict:
    f = pq.ParquetFile(L_FILE)
    groups = list(range(f.metadata.num_row_groups))
    t0 = time.time()
    arts = sents = 0
    hashes, samples = [], []
    with ProcessPoolExecutor(max(1, (os.cpu_count() or 2) - 1)) as pool:
        for k, (a, s, h, sm) in enumerate(pool.map(_row_group, groups), 1):
            arts += a
            sents += s
            hashes.append(h)
            samples.extend(sm[:4])
            if k % 20 == 0:
                print(f"  {k}/{len(groups)} row groups, {arts} articles, {sents} sentences", flush=True)
    secs = time.time() - t0
    distinct = int(np.unique(np.concatenate(hashes)).size) if hashes else 0
    out = {
        "articles": arts,
        "sentences": sents,
        "distinct": distinct,
        "seconds": round(secs, 1),
        "sentences_per_s": round(sents / secs, 1) if secs else None,
        "embed_note": "Embedding all of L needs a GPU; not run on the laptop.",
    }
    if os.environ.get("EMBED_BACKEND") in ("remote", "st") and sample_articles:
        from engine.embed import VectorStore, embed_texts

        texts = []
        for text in pq.read_table(L_FILE, columns=["text"]).slice(0, sample_articles).column("text").to_pylist():
            texts.extend(md_sentences(text))
        texts = list({claim_hash(t): t for t in texts}.values())
        t = time.time()
        embed_texts(texts, VectorStore(DATA / "emb-l"))
        rate = len(texts) / (time.time() - t)
        out.update(
            sample_articles=sample_articles,
            sample_sentences=len(texts),
            gpu_sentences_per_s=round(rate, 1),
            projected_hours_all_l=round(distinct / rate / 3600, 2),
            embed_note=f"Measured on the GPU: {rate:.0f} sentences/s, so all {distinct:,} distinct sentences "
            f"of L take about {distinct / rate / 3600:.1f} hours.",
        )
    (DATA / "l_scale.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=10_000)
    run(ap.parse_args().sample)
