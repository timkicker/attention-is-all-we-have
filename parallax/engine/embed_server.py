"""Embedding server for the Verda GPU instance (PLAN A6): POST /embed {texts} -> {vectors}.

Run on the GPU host: `uv sync --extra gpu && uv run uvicorn engine.embed_server:app --host 127.0.0.1 --port 9100`.
It listens on 127.0.0.1 only; the laptop reaches it with `ssh -L 9100:127.0.0.1:9100 <host>` and
EMBED_BACKEND=remote EMBED_URL=http://127.0.0.1:9100.
"""

import time

from fastapi import FastAPI
from pydantic import BaseModel

from engine.embed import STBackend

app = FastAPI(title="parallax-embed")
_be = STBackend()
_stats = {"texts": 0, "seconds": 0.0}


class EmbedIn(BaseModel):
    texts: list[str]


@app.post("/embed")
def embed(body: EmbedIn) -> dict:
    t = time.time()
    v = _be(body.texts)
    _stats["texts"] += len(body.texts)
    _stats["seconds"] += time.time() - t
    return {"vectors": v.tolist()}


@app.get("/health")
def health() -> dict:
    rate = _stats["texts"] / _stats["seconds"] if _stats["seconds"] else None
    return {"ok": True, **_stats, "texts_per_s": rate}
