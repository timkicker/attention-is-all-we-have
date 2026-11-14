import numpy as np

from contract.engine import DIM, claim_hash
from engine import embed as E


class FakeBackend:
    batch = 2

    def __init__(self):
        self.calls = 0

    def __call__(self, texts):
        self.calls += 1
        rng = np.random.default_rng(len(texts) + self.calls)
        return E._normalise(rng.standard_normal((len(texts), DIM)) * 7)


def test_vectors_have_1024_dims_and_unit_norm(tmp_path):
    be = FakeBackend()
    store = E.VectorStore(tmp_path)
    vecs = E.embed_texts(["one sentence here", "two sentence here", "three sentence here"], store, be)
    assert all(v.shape == (DIM,) for v in vecs)
    assert all(abs(np.linalg.norm(v) - 1) < 1e-3 for v in vecs)
    assert be.calls == 2  # batch of 2 then 1


def test_cached_text_causes_no_call_and_survives_reload(tmp_path):
    be = FakeBackend()
    store = E.VectorStore(tmp_path)
    first = E.embed_texts(["Same text."], store, be)[0]
    E.embed_texts(["same   TEXT."], store, be)  # same claim hash after normalisation
    assert be.calls == 1
    again = E.VectorStore(tmp_path)
    assert claim_hash("Same text.") in again
    assert np.allclose(again.get(claim_hash("Same text.")), first)


def test_ollama_backend_normalises(monkeypatch):
    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"embeddings": [[3.0] * DIM]}

    be = E.OllamaBackend("http://x")
    sent = {}
    monkeypatch.setattr(be.session, "post", lambda url, json, timeout: sent.update(json) or Resp())
    v = be(["a"])
    assert abs(np.linalg.norm(v[0]) - 1) < 1e-6
    assert sent["model"] == "bge-m3" and sent["options"]["num_ctx"] == 8192


def test_shared_store_loads_once_and_never_writes(tmp_path, monkeypatch):
    import threading

    seed = E.VectorStore(tmp_path)
    E.embed_texts(["Known sentence."], seed, FakeBackend())
    assert len(list(tmp_path.glob("shard-*.npz"))) == 1

    loads = []
    real_init = E.VectorStore.__init__

    def counting_init(self, root=None, persist=True):
        loads.append(persist)
        real_init(self, root, persist)

    monkeypatch.setattr(E, "EMB_DIR", tmp_path)
    monkeypatch.setattr(E, "_SHARED", None)
    monkeypatch.setattr(E.VectorStore, "__init__", counting_init)
    be = FakeBackend()
    monkeypatch.setattr(E, "backend", lambda: be)

    from engine.real import GeminiEngine

    eng = GeminiEngine()
    errors = []

    def call(i):
        try:
            eng.embed(["Known sentence.", f"New text number {i}."])
        except Exception as e:  # pragma: no cover - surfaced below
            errors.append(e)

    threads = [threading.Thread(target=call, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert loads == [False]  # one read-only load for the whole process
    assert len(list(tmp_path.glob("shard-*.npz"))) == 1  # the API path wrote nothing
    store = E.shared_store()
    assert claim_hash("Known sentence.") in store
    # a visitor's text is embedded for its request only (engine.embed.Overlay), so the process does not grow per call
    assert claim_hash("New text number 3.") not in store


def test_writer_shares_the_loaded_vectors_and_writes_new_shards(tmp_path, monkeypatch):
    seed = E.VectorStore(tmp_path)
    E.embed_texts(["Known sentence."], seed, FakeBackend())
    monkeypatch.setattr(E, "EMB_DIR", tmp_path)
    monkeypatch.setattr(E, "_SHARED", None)

    w = E.writer()
    assert w.vecs is E.shared_store().vecs  # one copy of data/emb/ per process
    E.embed_texts(["Ingested sentence."], w, FakeBackend())
    assert len(list(tmp_path.glob("shard-*.npz"))) == 2  # the ingest still persists its vectors
    assert claim_hash("Ingested sentence.") in E.shared_store()  # and the API sees them at once
