# Compute for Parallax

## Why compute was needed

Every distinct sentence of the Winter War history (seven editions) and every long-lived sentence of the Finnish dataset M needs a bge-m3 vector. On the laptop, Ollama embeds 19.98 sentences/s (measured on 10486 Winter War sentences), and 14.47 sentences/s on the longer Finnish sentences of M.

## The Verda GPU job

- Instance: `1A100.22V` (NVIDIA A100-SXM4-80GB), spot at 1.193 EUR/h in FIN-03, created and deleted through the Verda Public API (`pipeline/verda.py`).
- Setup: uv sync --extra gpu 33 s, first vector after 28 s (model download included).
- Job: `engine/embed_batch.py` on the GPU host, sentence-transformers `BAAI/bge-m3` in fp16, texts sorted by length, batch 256, vectors L2-normalised.

| Work | Sentences | Seconds | Sentences/s |
|---|---|---|---|
| Long-lived sentences of M (alive, or lived a year or more) | 800365 | 175.7 | 4555.2 |
| Sample of L (10000 articles) | 751261 | 169.5 | 4433.0 |
| Laptop, Ollama, same model | | | 14.47 |

The GPU is about 315 times faster than the laptop. Credits spent: 0.38 EUR.

What failed: The spot instance was evicted while the M vectors were being downloaded; the vectors were lost, the measurements were kept. On-demand single-GPU types were not available at the time.

## Path to scale

Dataset L (568416 current Finnish articles) splits into 10204233 distinct sentences (at the measured 4433.0 sentences/s one A100 embeds them in about 38 minutes, about 0.76 EUR at the spot price). The same job runs over more language editions, re-embedding only sentences whose hash is new each night. Parallax reads and compares only; there are no automated edits at any scale.

