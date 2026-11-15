"""The local semantic search only proposes candidates (matching/semantic.py). Offline and fast: a fake embedder
with hand-set vectors stands in for the model. One test reads the real model and skips when it is not here."""

import logging
from datetime import date

import numpy as np
import pytest

from validio.matching import semantic
from validio.matching.semantic import Blend, Index, blend

TODAY = date(2026, 11, 14)


class Fake:
    """Phrases to vectors from a table; the rows are normalised like the model's."""

    def __init__(self, table: dict[str, list[float]]):
        self.table = table

    def embed(self, texts):
        v = np.array([self.table[t] for t in texts], dtype=np.float32)
        return v / np.linalg.norm(v, axis=1, keepdims=True)


def unit(*xs: float) -> np.ndarray:
    v = np.array(xs, dtype=np.float32)
    return v / np.linalg.norm(v)


def index(rows: dict[str, list[float]], phrases: dict[str, list[float]]) -> Index:
    return Index(list(rows), np.stack([unit(*v) for v in rows.values()]), Fake(phrases))


# the merge, on its own


def test_keyword_hits_that_score_near_the_best_are_high_and_nothing_is_added():
    b = blend({"a": 0.90, "b": 0.88, "c": 0.70}, [("a", 0.90), ("x", 0.89), ("b", 0.88)])
    assert b == Blend(frozenset({"a", "b"}), (), False)


def test_with_no_keyword_hit_the_nearest_products_are_added_first():
    b = blend({}, [("x", 0.90), ("y", 0.88), ("z", 0.80)])
    assert b.extra == ("x", "y") and b.first  # z is too far below the best


def test_few_keyword_hits_get_company_after_them():
    b = blend({"a": 0.86}, [("x", 0.88), ("a", 0.86), ("y", 0.85)])
    assert b.extra == ("x", "y") and not b.first and b.high == {"a"}


def test_a_keyword_path_far_below_the_best_looks_off_and_the_meaning_goes_first():
    b = blend({"a": 0.70, "b": 0.71, "c": 0.69}, [("x", 0.90), ("y", 0.88)])
    assert b.extra == ("x", "y") and b.first and not b.high


def test_below_the_floor_nothing_is_proposed():
    assert blend({}, [("x", 0.60), ("y", 0.59)]) == Blend(frozenset(), (), False)


def test_search_and_scores_with_a_fake_embedder():
    idx = index({"a": [1, 0, 0], "b": [0.9, 0.1, 0], "c": [0, 1, 0]}, {"q": [1, 0, 0]})
    hits = idx.search("q", k=2)
    assert [i for i, _ in hits] == ["a", "b"] and hits[0][1] == pytest.approx(1.0)
    assert idx.scores("q", ["c", "zz"]) == {"c": pytest.approx(0.0), "zz": 0.0}


def test_save_and_load_round_trip(tmp_path):
    p = tmp_path / "e.npz"
    semantic.save(p, ["a", "b"], np.stack([unit(1, 0), unit(0, 1)]))
    idx = semantic.load(p, Fake({}))
    assert idx.ids == ["a", "b"] and idx.model == semantic.MODEL and idx.vecs.dtype == np.float32


# the switch


def test_off_by_default_in_tests():
    assert semantic.for_catalog() is None


def test_on_without_the_embeddings_file_is_keyword_only_with_a_log_line(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("VALIDIO_SEMANTIC", "1")
    monkeypatch.setenv("VALIDIO_EMBEDDINGS", str(tmp_path / "none.npz"))
    with caplog.at_level(logging.WARNING, logger="validio.matching.semantic"):
        assert semantic.for_catalog() is None
    assert "make embed" in caplog.text


# with the catalogue: what it proposes still goes through the screening

WHIPPING = "464194"  # Valio whipping cream 1 l UHT lactose free
PLAIN_CREAM = "469050"  # Valio Keittiön whipping cream 2 dl, no lactose-free claim


def test_a_phrase_no_catalogue_word_names_gets_candidates_by_meaning(catalog, monkeypatch):
    from validio.matching.need import parse_need, screen

    idx = index({WHIPPING: [1, 0, 0], PLAIN_CREAM: [0.97, 0.2, 0]},
                {"zzyzx frobnicator": [1, 0.05, 0], "lactose-free zzyzx frobnicator": [1, 0.05, 0]})
    monkeypatch.setattr(semantic, "for_catalog", lambda cat=None: idx)
    n = parse_need("10 litres of zzyzx frobnicator", TODAY, catalog)
    assert n.kind == n.phrase == "zzyzx frobnicator"
    kept, dropped = screen(n, catalog)
    assert [p.id for p in kept] == [WHIPPING, PLAIN_CREAM] and not dropped
    assert n.by_meaning == {WHIPPING, PLAIN_CREAM}
    # the request's own diet still screens: the cream without the claim is not proposed
    lf = parse_need("10 litres of lactose-free zzyzx frobnicator", TODAY, catalog)
    assert [p.id for p in screen(lf, catalog)[0]] == [WHIPPING]


def test_without_the_index_the_same_phrase_is_refused(catalog):
    from validio.matching.need import parse_need

    with pytest.raises(ValueError, match="no known product kind"):
        parse_need("10 litres of zzyzx frobnicator", TODAY, catalog)


def test_keyword_hits_that_score_high_go_first_when_the_cap_cuts(catalog):
    from validio.matching.need import parse_need, screen

    n = parse_need("200 litres of cream", TODAY, catalog)
    everything = screen(n, catalog, limit=None, sem=None)[0]
    assert len(everything) > 3
    last = everything[-1].id  # the one the keyword order puts last
    rows = {p.id: [0.2, 1, 0] for p in everything}
    rows[last] = [1, 0, 0]
    idx = index(rows, {"cream": [1, 0, 0]})
    kept, _ = screen(n, catalog, limit=3, sem=idx)
    assert kept[0].id == last and not n.by_meaning  # reordered, nothing added


def test_search_products_meaning_joins_the_words_inside_the_category(catalog):
    from validio.matching.need import search_catalog

    idx = index({WHIPPING: [1, 0, 0], "461219": [0.99, 0.1, 0]}, {"frobnicate": [1, 0, 0]})
    assert search_catalog(catalog, "frobnicate", sem=None) == []
    assert [p.id for p in search_catalog(catalog, "frobnicate", sem=idx)] == [WHIPPING, "461219"]
    assert [p.id for p in search_catalog(catalog, "frobnicate", category="104", sem=idx)] == [WHIPPING]


# a product only the meaning proposed never orders without a person (Cedar: a substitute outside Valio's list)


def test_a_candidate_by_meaning_waits_for_a_person_where_the_same_by_name_orders(catalog, tmp_path, monkeypatch):
    from test_kitchen_diet import MON, NOW, Invented, demo_mandate

    from validio.audit.log import AuditLog
    from validio.orders.service import OrderService
    from validio.orders.store import Store
    from validio.orders.supply import BY_MEANING, LineRequest, SupplyService

    def ask(text: str, db: str) -> dict:
        svc = OrderService(Store(tmp_path / db), catalog, Invented(catalog), AuditLog(tmp_path / db), clock=lambda: NOW)
        return SupplyService(svc).request_supply(mandate=demo_mandate(), lines=[LineRequest(text=text)], deliver_by=MON,
                                                 idempotency_key=db)

    by_name = ask("10 litres of whipping cream", "a.db")
    assert by_name["decision"]["outcome"] == "auto_order", by_name["decision"]
    idx = index({WHIPPING: [1, 0, 0]}, {"frobnicator": [1, 0, 0]})
    monkeypatch.setattr(semantic, "for_catalog", lambda cat=None: idx)
    req = ask("10 litres of frobnicator", "b.db")
    (line,) = req["lines"]
    (opt,) = line["options"]
    assert opt["productId"] == WHIPPING and opt["isSubstitute"] and opt["onValioList"] is False
    assert opt["sentence"].startswith(BY_MEANING)
    assert line["chosen"]["isSubstitute"] is True
    assert req["status"] == "waiting", req["decision"]
    assert "not on Valio's list" in req["decision"]["sentence"]


# the real model, when `make embed` ran on this machine


def test_the_local_model_finds_bouillon_for_vegetable_stock(catalog, monkeypatch):
    from validio.config import embeddings_path, models_dir

    pytest.importorskip("fastembed")
    if not embeddings_path().is_file() or not models_dir().is_dir():
        pytest.skip("no local model: make embed")
    monkeypatch.setenv("VALIDIO_SEMANTIC", "1")
    idx = semantic.for_catalog(catalog)
    if idx is None:
        pytest.skip("the local model did not load")
    names = [catalog.get(i).name_en.lower() for i, _ in idx.search("vegetable bouillon", k=5)]
    assert sum("bouillon" in n or "fond" in n for n in names) >= 3, names
