"""bge-m3 sentence vectors from one of three backends, always L2-normalised (PLAN A6).

EMBED_BACKEND=ollama  POST EMBED_URL/api/embed, model bge-m3, batches of 32 (laptop)
EMBED_BACKEND=st      sentence-transformers BAAI/bge-m3 in this process, fp16, batch 128 (GPU)
EMBED_BACKEND=remote  POST EMBED_URL/embed {texts} to engine.embed_server (Verda GPU through an ssh tunnel)

VectorStore keeps every vector on disk under data/emb/ keyed by claim hash, so a text is embedded once. The batch
pipeline writes new shards; the API process uses shared_store(), loaded once per process and never written.
"""

import os
import threading
from pathlib import Path

import numpy as np
import requests

from contract.db import load_env
from contract.engine import DIM, claim_hash

ROOT = Path(__file__).resolve().parent.parent
EMB_DIR = ROOT / "data" / "emb"
MODEL = "bge-m3"


def _normalise(vecs) -> np.ndarray:
    a = np.asarray(vecs, dtype=np.float32)
    if a.ndim != 2 or a.shape[1] != DIM:
        raise ValueError(f"expected (n, {DIM}) vectors, got {a.shape}")
    n = np.linalg.norm(a, axis=1, keepdims=True)
    n[n == 0] = 1
    return a / n


class OllamaBackend:
    batch = 32

    def __init__(self, url: str, timeout: float = 600) -> None:
        self.url = url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    def __call__(self, texts: list[str]) -> np.ndarray:
        r = self.session.post(
            f"{self.url}/api/embed",
            json={"model": MODEL, "input": texts, "options": {"num_ctx": 8192, "num_batch": 8192}},
            timeout=self.timeout,
        )
        r.raise_for_status()
        return _normalise(r.json()["embeddings"])


class RemoteBackend:
    batch = 256

    def __init__(self, url: str, timeout: float = 600) -> None:
        self.url = url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    def __call__(self, texts: list[str]) -> np.ndarray:
        r = self.session.post(f"{self.url}/embed", json={"texts": texts}, timeout=self.timeout)
        r.raise_for_status()
        return _normalise(r.json()["vectors"])


class STBackend:
    batch = 128
    _lock = threading.Lock()
    _model = None

    def __call__(self, texts: list[str]) -> np.ndarray:
        with self._lock:
            if STBackend._model is None:
                from sentence_transformers import SentenceTransformer  # gpu extra only

                STBackend._model = SentenceTransformer("BAAI/bge-m3", device="cuda")
                STBackend._model.half()
        v = STBackend._model.encode(texts, batch_size=self.batch, normalize_embeddings=True, convert_to_numpy=True)
        return _normalise(v)


def backend(timeout: float = 600):
    """The configured backend; timeout (seconds) bounds each ollama or remote request."""
    load_env()
    kind = os.environ.get("EMBED_BACKEND") or "ollama"
    url = os.environ.get("EMBED_URL") or "http://127.0.0.1:11434"
    if kind == "ollama":
        return OllamaBackend(url, timeout)
    if kind == "remote":
        return RemoteBackend(url, timeout)
    if kind == "st":
        return STBackend()
    raise ValueError(f"EMBED_BACKEND must be ollama, st or remote, not {kind!r}")


class VectorStore:
    """Vectors by claim hash in npz shards under data/emb/. Appends a shard per flush.

    persist=False keeps new vectors in memory only: flush() never writes, so readers in parallel never race on a
    shard file name."""

    def __init__(self, root: Path | None = None, persist: bool = True) -> None:
        self.root = root or EMB_DIR
        self.persist = persist
        self.vecs: dict[str, np.ndarray] = {}
        self._pending: dict[str, np.ndarray] = {}
        self._shards = 0
        if self.root.exists():
            for p in sorted(self.root.glob("shard-*.npz")):
                z = np.load(p)
                for h, v in zip(z["h"], z["v"], strict=True):
                    self.vecs[str(h)] = v
                self._shards += 1

    def __contains__(self, h: str) -> bool:
        return h in self.vecs

    def __len__(self) -> int:
        return len(self.vecs)

    def get(self, h: str) -> np.ndarray | None:
        return self.vecs.get(h)

    def put(self, h: str, v: np.ndarray) -> None:
        self.vecs[h] = v
        if not self.persist:
            return
        self._pending[h] = v
        if len(self._pending) >= 4096:
            self.flush()

    def flush(self) -> None:
        if not self._pending:
            return
        self.root.mkdir(parents=True, exist_ok=True)
        hs = np.array(list(self._pending), dtype="U16")
        vs = np.stack(list(self._pending.values())).astype(np.float32)
        path = self.root / f"shard-{self._shards:05d}.npz"
        tmp = path.with_suffix(".tmp.npz")
        np.savez(tmp, h=hs, v=vs)
        tmp.replace(path)
        self._shards += 1
        self._pending = {}


_SHARED: VectorStore | None = None
_SHARED_LOCK = threading.Lock()


def shared_store() -> VectorStore:
    """The read-only store of this process: data/emb/ is read on first use only, new vectors stay in memory."""
    global _SHARED
    if _SHARED is None:
        with _SHARED_LOCK:
            if _SHARED is None:
                _SHARED = VectorStore(persist=False)
    return _SHARED


def embed_texts(texts: list[str], store: VectorStore | None = None, be=None, progress=None) -> list[np.ndarray]:
    """Vectors for texts, from the store when present; new ones are embedded in backend batches and stored."""
    store = store if store is not None else VectorStore()
    hs = [claim_hash(t) for t in texts]
    todo: dict[str, str] = {}
    for h, t in zip(hs, texts, strict=True):
        if h not in store and h not in todo:
            todo[h] = t
    if todo:
        be = be or backend()
        items = list(todo.items())
        for i in range(0, len(items), be.batch):
            chunk = items[i : i + be.batch]
            vecs = be([t for _, t in chunk])
            for (h, _), v in zip(chunk, vecs, strict=True):
                store.put(h, v)
            if progress:
                progress(min(i + be.batch, len(items)), len(items))
        store.flush()
    return [store.get(h) for h in hs]
