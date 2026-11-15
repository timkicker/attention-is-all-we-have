"""Local semantic search over the catalogue's product names: it proposes candidates, it never decides.

A small English embedding model (BAAI/bge-small-en-v1.5, quantised ONNX through fastembed, about 67 MB, CPU only)
turns each product's English name and its group name into a vector once (`make embed`, data/embeddings.npz).
A request's product phrase is turned into a vector on this machine and compared with them by cosine. Nothing,
neither a product nor a request, leaves the machine; the model files sit in data/models.

What it finds only joins the keyword candidates (need.screen): every product still goes through the same static
screening, diet and allergen grading, Valio's price and stock and the Cedar rules. A score never orders anything.

Off unless VALIDIO_SEMANTIC=1, and off without a word when fastembed, the model or the embeddings file is missing
(one log line says so): matching is then keyword only, as before.
"""

from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from ..catalog.groups import group_name
from ..config import embeddings_path, models_dir, semantic_on

if TYPE_CHECKING:
    import numpy as np

    from ..catalog.store import Catalog

log = logging.getLogger(__name__)

MODEL = "BAAI/bge-small-en-v1.5"
TOP_K = 40  # nearest products read per phrase, before screening
# cosine thresholds for bge-small, set on the before/after phrases (docs/ARCHITECTURE.md): its scores sit close
# together, an unrelated product often scores 0.70, so the bands are narrow
FLOOR = 0.72  # below this a product is not proposed at all
BAND = 0.03  # a keyword hit this close to the best score counts as a high one and goes first in the cap
ADD_BAND = 0.04  # semantic-only products this close to the best score are added
OFF = 0.10  # the best keyword hit this far below the best score: the keyword path looks off
FEW = 2  # fewer keyword candidates than this: semantic-only products are added


class Embedder(Protocol):
    def embed(self, texts: Sequence[str]) -> np.ndarray:
        """One L2-normalised row per text."""


def product_text(name: str, category: str) -> str:
    """What a product is embedded as: its English name and the plain name of its group, for context
    ("knorr vegetable bouillon 5kg/333l (in sauces, dressings and stock)")."""
    return f"{name} (in {group_name(category)})".lower()


class FastEmbedder:
    """bge-small through fastembed's ONNX runtime on the CPU. `local_only`: never downloads, the request path
    runs on what `make embed` fetched."""

    def __init__(self, cache_dir: Path, local_only: bool = True):
        from fastembed import TextEmbedding

        self.model = TextEmbedding(MODEL, cache_dir=str(cache_dir), local_files_only=local_only)

    def embed(self, texts: Sequence[str], batch_size: int = 256) -> np.ndarray:
        import numpy as np

        v = np.asarray(list(self.model.embed(list(texts), batch_size=batch_size)), dtype=np.float32)
        return v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-12)


@dataclass(frozen=True)
class Blend:
    """How semantic hits join the keyword candidates."""

    high: frozenset[str]  # keyword ids that also score near the best: they go first when the cap cuts
    extra: tuple[str, ...]  # semantic-only ids to add, best first; each is still screened
    first: bool  # the keyword path found nothing or looks off: the extra ids go before the keyword ones


def blend(keyword: dict[str, float], hits: Sequence[tuple[str, float]], *, few: int = FEW, band: float = BAND,
          add_band: float = ADD_BAND, off: float = OFF, floor: float = FLOOR) -> Blend:
    """`keyword`: the keyword candidates and their scores, in keyword order. `hits`: the nearest products of
    the whole catalogue, best first. Semantic-only products are added only when the keyword path finds fewer
    than `few` or its best is `off` below the best hit; then those within `add_band` of the best and above
    `floor`."""
    top = max([s for _, s in hits[:1]] + list(keyword.values()), default=0.0)
    if top < floor:
        return Blend(frozenset(), (), False)
    high = frozenset(i for i, s in keyword.items() if s >= top - band)
    looks_off = bool(keyword) and max(keyword.values()) < top - off
    if len(keyword) >= few and not looks_off:
        return Blend(high, (), False)
    extra = tuple(i for i, s in hits if i not in keyword and s >= floor and s >= top - add_band)
    return Blend(high, extra, looks_off or not keyword)


class Index:
    """Product vectors in memory (rows L2-normalised) and the embedder for the phrases."""

    def __init__(self, ids: Sequence[str], vecs: np.ndarray, embedder: Embedder, model: str = MODEL):
        self.ids, self.vecs, self.embedder, self.model = list(ids), vecs, embedder, model
        self.pos = {pid: i for i, pid in enumerate(self.ids)}
        self._queries: OrderedDict[str, np.ndarray] = OrderedDict()
        self._lock = threading.Lock()

    def _vec(self, text: str) -> np.ndarray:
        text = " ".join(text.lower().split())
        with self._lock:
            if text in self._queries:
                self._queries.move_to_end(text)
                return self._queries[text]
        v = self.embedder.embed([text])[0]
        with self._lock:
            self._queries[text] = v
            if len(self._queries) > 512:
                self._queries.popitem(last=False)
        return v

    def search(self, text: str, k: int = TOP_K) -> list[tuple[str, float]]:
        """The `k` nearest products to the phrase, best first."""
        import numpy as np

        sims = self.vecs @ self._vec(text)
        k = min(k, len(self.ids))
        if k <= 0:
            return []
        top = np.argpartition(-sims, k - 1)[:k]
        top = top[np.argsort(-sims[top], kind="stable")]
        return [(self.ids[i], float(sims[i])) for i in top]

    def scores(self, text: str, ids: Sequence[str]) -> dict[str, float]:
        """Each product's score for the phrase, in the given order; 0 for a product without a vector."""
        q = self._vec(text)
        return {pid: float(self.vecs[self.pos[pid]] @ q) if pid in self.pos else 0.0 for pid in ids}


def save(path: Path, ids: Sequence[str], vecs: np.ndarray, model: str = MODEL) -> None:
    import numpy as np

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp.npz")
    np.savez(tmp, ids=np.array(list(ids)), vecs=vecs.astype(np.float16), model=np.array(model))
    tmp.replace(path)


def load(path: Path, embedder: Embedder) -> Index:
    import numpy as np

    with np.load(path, allow_pickle=False) as f:
        vecs = f["vecs"].astype(np.float32)
        return Index([str(i) for i in f["ids"]], vecs, embedder, str(f["model"]))


_ACTIVE: dict[tuple[str, float], Index | None] = {}
_LOAD = threading.Lock()


def _open(path: Path) -> Index | None:
    if not path.is_file():
        log.warning("semantic search off: %s missing, run make embed (keyword matching only)", path)
        return None
    try:
        idx = load(path, FastEmbedder(models_dir()))
    except Exception as e:  # noqa: BLE001 fastembed missing, the model not fetched, a broken file: keyword only
        log.warning("semantic search off: %s (keyword matching only; uv sync --extra semantic, make embed)", e)
        return None
    if idx.model != MODEL:
        log.warning("semantic search off: %s was made with %s, not %s; run make embed", path, idx.model, MODEL)
        return None
    log.info("semantic search on: %d products, %s, local", len(idx.ids), MODEL)
    return idx


def for_catalog(cat: Catalog | None = None) -> Index | None:
    """The local index when VALIDIO_SEMANTIC=1 and it can be loaded, else None. Loaded once per file."""
    if not semantic_on():
        return None
    path = embeddings_path()
    key = (str(path), path.stat().st_mtime if path.is_file() else 0.0)
    with _LOAD:
        if key not in _ACTIVE:
            _ACTIVE[key] = _open(path)
        return _ACTIVE[key]


def warm() -> None:
    """Load the model and the vectors before the first request needs them (the app starts it in a thread)."""
    if (idx := for_catalog()) is not None:
        idx.search("milk", k=1)
