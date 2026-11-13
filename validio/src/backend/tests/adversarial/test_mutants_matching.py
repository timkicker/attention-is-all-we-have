"""Tests written to kill mutants that survived mutmut in matching/rank.py and matching/substitute.py
(docs/TESTING.md). Synthetic products and a fake catalog and Valio, no data needed."""

from dataclasses import replace
from datetime import date, datetime, timedelta

import pytest

from validio.catalog.model import Product
from validio.matching.need import Need, Ranked
from validio.matching.rank import best_pick, rank_one
from validio.matching.substitute import (
    SubVerdict,
    _judge,
    _kept,
    blend_note,
    diet_break,
    measured_need,
    safe_swap,
)
from validio.valio.budget import CallBudget
from validio.valio.models import Availability, Quote, ScheduleLine

NOW = datetime.fromisoformat("2026-11-14T10:00:00+02:00")
MON = date(2026, 11, 16)
LF = "FREE_FROM_LACTOSE"


def prod(pid="P-1", *, name="test milk 1 l", claims=(LF,), contains=(), lacs=0.0, kg=None, litres=1.0,
         sales_unit="ST", reliability=None, carbon=None, labels=(), subs=(), category="10400"):
    return Product(
        id=pid, name_en=name, name_fi=None, category=category, vendor="Valio", sales_unit=sales_unit,
        base_unit="ST", units={"ST": 1.0}, base_volume_l=litres, base_weight_kg=kg, claims=frozenset(claims),
        contains=frozenset(contains), may_contain=frozenset(), free_from=frozenset(), has_allergen_data=True,
        lacs_g=lacs, key_ingredients_en=None, marketing_en=None, planted_en=None, substitutes=tuple(subs),
        reliability=reliability, carbon_kg_per_kg=carbon, labels=frozenset(labels), temperature=None,
        deleted=False)


def quote(pid="P-1", price=100, error=False, comparison=None, unit=None):
    return Quote(pid, error, price, None, True, price, comparison, unit, 0.14)


def avail(pid="P-1", amount=1000.0, day=MON, closing=NOW + timedelta(hours=5), lines=1):
    ln = [ScheduleLine(amount, day, "ST", False) for _ in range(lines)]
    return Availability(pid, "Stock", closing, False, ln, NOW)


def need(qty=3, unit="L", claims=(LF,), kind="milk", pid=None):
    return Need(kind, qty, unit, set(claims), set(), MON, None, product_id=pid)


# rank_one

def test_rank_one_unchecked_note_and_no_note_when_consistent():
    # `elif level != UNCHECKED` adds the note to every checked claim; notes.append(None)
    ok = rank_one(need(), prod(), quote(), avail(), NOW)
    assert ok.accepted and ok.notes == []
    unchecked = rank_one(need(), prod(lacs=None), quote(), avail(), NOW)
    assert unchecked.notes == ["Lactose free claim unchecked: claims lactose free but gives no lactose value"]


def test_rank_one_exact_rejection_sentences():
    r = rank_one(need(claims=(LF, "ORGANIC")), prod(claims=(), contains=("ML",), lacs=4.7), None, None, NOW)
    assert r.reasons == [
        "Not lactose free: lists lactose as contained and lactose 4.7 g per 100 g",
        "No ORGANIC claim in Valio's data",  # unknown claims keep their code as the name
        "Valio has no price for it",
        "Valio gives no delivery date for it",
    ]
    assert not r.accepted and r.total_cents is None


def test_rank_one_quote_error_with_a_price_is_no_price():
    # `q.error or price is None` -> `and`; `q is None or q.error` -> `and`
    r = rank_one(need(), prod(), quote(error=True), avail(), NOW)
    assert r.reasons == ["Valio has no price for it"]


def test_rank_one_quote_without_price_does_not_crash():
    # `if q and price is not None` -> `or`: sales_qty * None
    r = rank_one(need(), prod(), quote(price=None), avail(), NOW)
    assert r.total_cents is None and r.sales_qty == 3 and r.reasons == ["Valio has no price for it"]


def test_rank_one_pack_size_from_comparison_price():
    # amount_per_sales_unit(need, p, None): the only pack size source is the quote
    p = prod(name="test milk", litres=None)
    r = rank_one(need(qty=6), p, quote(price=300, comparison=150, unit="L"), avail(), NOW)
    assert (r.sales_qty, r.total_cents, r.accepted) == (3, 900, True)


def test_rank_one_float_noise_does_not_add_a_pack():
    # round(..., 6) -> round(..., 7)
    r = rank_one(need(qty=3.0000004), prod(), quote(), avail(), NOW)
    assert r.sales_qty == 3


def test_rank_one_unknown_stock_note_and_late_delivery_sentence():
    a = Availability("P-1", "Terminal", NOW + timedelta(hours=5), False,
                     [ScheduleLine(999999.0, date(2026, 11, 20), "ST", False)], NOW)
    r = rank_one(need(), prod(), quote(), a, NOW)
    assert r.notes == ["the quantity is unknown"]
    assert r.reasons == ["Earliest delivery 20 Nov, after 16 Nov"]


# best_pick

def _ok(pid, total, **kw):
    return Ranked(prod(pid, **kw), 1, total, True)


def _order(options, **kw):
    return [r.product.id for r in best_pick(options, **kw)]


def test_tie_band_edge_is_inside():
    # `total <= cheapest * 1.05` -> `<`: exactly 5 % more is still a tie, so reliability decides
    a, b = _ok("A", 10000, reliability=0.5), _ok("B", 10500, reliability=0.9)
    assert _order([a, b]) == ["B", "A"]


def test_zero_reliability_sorts_after_some_reliability():
    # -(reliability or 0) -> -(reliability or 1): 0.0 would rank like 1.0
    assert _order([_ok("A", 100, reliability=0.0), _ok("B", 100, reliability=0.5)]) == ["B", "A"]


def test_carbon_known_before_unknown_then_lower_first():
    # carbon is None -> is not None; `carbon or 0` -> `and 0` / `or 1`
    assert _order([_ok("A", 100), _ok("B", 100, carbon=2.0)]) == ["B", "A"]
    assert _order([_ok("A", 100, carbon=2.0), _ok("B", 100, carbon=1.0)]) == ["B", "A"]
    assert _order([_ok("A", 100, carbon=0.5), _ok("B", 100, carbon=0.0)]) == ["B", "A"]


def test_rejected_options_sort_priced_first_then_by_price():
    # rejected key: `total is None` -> `is not None`; `total or 0` -> `total and 0`
    no_price = Ranked(prod("A"), None, None, False, ["Valio has no price for it"])
    dear = Ranked(prod("B"), 1, 900, False, ["x"])
    cheap = Ranked(prod("C"), 1, 100, False, ["y"])
    assert _order([no_price, dear, cheap]) == ["C", "B", "A"]


def test_rejected_without_reasons_says_not_usable():
    r = Ranked(prod("A"), None, None, False, [])
    assert best_pick([r])[0].why == ["Not usable"]


# substitute.py: sentences and verdicts

def test_diet_break_sentences():
    assert diet_break(prod(claims=(), contains=("AM",)), {LF}) == \
        "Lists milk and has no lactose-free claim in Valio's data"
    # `code and code in contains` -> `or`: no milk listed, so it only lacks the claim
    assert diet_break(prod(claims=()), {LF}) == "No lactose-free claim in Valio's data"
    assert diet_break(prod(), {"ORGANIC"}) == "No organic claim in Valio's data"
    assert diet_break(prod(contains=("ML",)), {LF}) == "Not lactose free: lists lactose as contained"
    assert diet_break(prod(), {LF}) is None


def test_kept_sentences():
    assert _kept(prod(), set()) == "Keeps the line's rules"
    assert _kept(prod(), {LF}) == "Lactose free and checked"
    assert _kept(prod(lacs=None), {LF}) == "Lactose free, claim unchecked"
    assert _kept(prod(claims=(LF, "ORGANIC")), {LF, "ORGANIC"}) == "Lactose free and organic, claim unchecked"


def test_measured_need_pieces_to_litres_keeps_decimals():
    # unit "L" mutated away; round(x, None) drops the decimals
    n = measured_need(need(qty=3, unit="PCS"), prod(name="test milk", litres=0.5))
    assert (n.quantity, n.unit) == (1.5, "L")
    assert measured_need(need(qty=3, unit="PCS"), prod(name="test cheese", litres=None, kg=0.25)).unit == "KG"
    assert measured_need(need(qty=3, unit="L"), prod()).quantity == 3


def test_blend_note_ignores_case():
    n = need(kind="mozzarella", unit="KG")
    assert blend_note(prod(name="Mozzarella-Fontal 1 kg"), n) == "A mozzarella-fontal blend, not pure mozzarella"
    assert blend_note(prod(name="Mozzarella 1 kg"), n) is None


def _ranked(**kw):
    return rank_one(need(), prod(**kw), quote(), avail(), NOW)


def test_judge_every_verdict():
    p = prod()
    ok = _judge(p, _ranked(), need(), True)
    assert (ok.verdict, ok.on_valio_list, ok.product) == (SubVerdict.OK_LISTED, True, p)
    assert ok.sentence == "Lactose free and checked. 3 packs for 3.00 €, on Valio's substitute list"
    assert ok.ranked is not None

    out = _judge(p, _ranked(), need(), False)
    assert (out.verdict, out.on_valio_list) == (SubVerdict.OUTSIDE_LIST, False)
    assert out.sentence == "Lactose free and checked. 3 packs for 3.00 €"

    r = rank_one(need(), p, quote(), None, NOW)
    und = _judge(p, r, need(), True)
    assert (und.verdict, und.on_valio_list, und.ranked) == (SubVerdict.UNDELIVERABLE, True, r)
    assert und.sentence == "Lactose free and checked, but Valio gives no delivery date for it"

    r = rank_one(need(), p, quote(price=None), avail(), NOW)
    rej = _judge(p, r, need(), False)
    assert (rej.product, rej.verdict, rej.on_valio_list, rej.ranked) == (p, SubVerdict.REJECTED, False, r)
    r2 = rank_one(need(qty=5000), p, None, avail(), NOW)
    assert _judge(p, r2, need(qty=5000), True).sentence == \
        "Valio has no price for it. Only 1,000 packs in stock, 5,000 needed"


def test_judge_blend_note_goes_to_notes():
    n = need(kind="mozzarella", unit="KG", qty=1)
    p = prod(name="Mozzarella-Fontal", litres=None, kg=1.0, category="106")
    r = rank_one(n, p, quote(), avail(), NOW)
    o = _judge(p, r, n, True)
    assert r.notes == ["A mozzarella-fontal blend, not pure mozzarella"]
    assert o.sentence.startswith("Lactose free and checked. A mozzarella-fontal blend, not pure mozzarella. ")


# substitute.py: safe_swap with a fake catalog and Valio

class FakeCatalog:
    def __init__(self, products):
        self.by_id = {p.id: p for p in products}

    def get(self, pid):
        return self.by_id.get(pid)

    def search(self, text=None, category_prefix=None, claims=None, limit=50):
        out = [p for p in sorted(self.by_id.values(), key=lambda p: p.id)
               if (not text or text in p.name_en.lower())
               and (not category_prefix or p.category.startswith(category_prefix))]
        return out[:limit]

    def substitutes_of(self, pid):
        return [self.by_id[i] for i in self.by_id[pid].substitutes if i in self.by_id]


class FakeValio:
    def __init__(self, undeliverable=()):
        self.undeliverable = set(undeliverable)

    def price(self, ids, requested, budget):
        return {i: quote(i) for i in ids}

    def availability(self, ids, requested, budget):
        return {i: avail(i) for i in ids if i not in self.undeliverable}


def _swap(products, original, valio=None, **kw):
    cat = FakeCatalog(products)
    return safe_swap(cat.get(original), need(), cat, valio or FakeValio(), MON, CallBudget(40), NOW, **kw)


def test_safe_swap_searches_outside_by_default_and_keeps_flags():
    orig = prod("O", subs=("S1", "S2"))
    blocked = prod("S1", claims=(), contains=("AM",))
    late = prod("S2")
    outside = prod("X")
    r = _swap([orig, blocked, late, outside], "O", FakeValio(undeliverable={"S2"}))
    assert r.original is orig
    assert [(o.product.id, o.verdict, o.on_valio_list) for o in r.listed] == [
        ("S1", SubVerdict.BLOCKED_DIET, True), ("S2", SubVerdict.UNDELIVERABLE, True)]
    assert r.searched_outside is True
    # neither the original nor a listed substitute comes back as an extra id
    assert r.extra_ids == ["X"]
    assert [(o.product.id, o.verdict, o.on_valio_list) for o in r.outside] == [("X", SubVerdict.OUTSIDE_LIST, False)]
    assert r.needs_person and r.best.product.id == "X"


def test_safe_swap_outside_search_is_not_cut_at_twelve():
    # screen(limit=None) -> default 12: twelve listed, blocked and better-ranked products would fill the screen
    subs = [prod(f"S{i:02}", contains=("ML",), reliability=1.0) for i in range(12)]
    orig = prod("O", subs=[s.id for s in subs])
    tail = prod("Z", reliability=0.1)
    r = _swap([orig, *subs, tail], "O")
    assert all(o.verdict is SubVerdict.BLOCKED_DIET for o in r.listed)
    assert r.extra_ids == ["Z"]


@pytest.mark.parametrize("search", [True, False])
def test_safe_swap_listed_ok_stops(search):
    orig = prod("O", subs=("S1",))
    r = _swap([orig, prod("S1"), prod("X")], "O", search_outside=search)
    assert r.searched_outside is False and r.extra_ids == [] and r.best.product.id == "S1"
    assert not r.needs_person
    assert replace(r.best.product) == r.listed[0].product
