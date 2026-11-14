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
