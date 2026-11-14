"""Diet claims against more cereal and meat words and listed oats. No Valio data needed."""

from dataclasses import replace

import pytest

from validio.catalog.model import Product
from validio.trust.claims import claim_check
from validio.trust.levels import TrustLevel

BASE = Product(
    id="T-1", name_en="test", name_fi=None, category="10600", vendor="x", sales_unit="ST", base_unit="ST",
    units={"ST": 1.0}, base_volume_l=None, base_weight_kg=0.5, claims=frozenset(), contains=frozenset(),
    may_contain=frozenset(), free_from=frozenset(), has_allergen_data=True, lacs_g=None, key_ingredients_en=None,
    marketing_en=None, planted_en=None, substitutes=(), reliability=None, carbon_kg_per_kg=None, labels=frozenset(),
    temperature=None, deleted=False)


@pytest.mark.parametrize("text", ["salami (pork)", "lard", "ANCHOVY paste", "naudanliha 30%", "kyckling", "chorizo"])
def test_vegetarian_claim_is_contradicted_by_more_meat_words(text):
    p = replace(BASE, claims=frozenset({"VEGETARIAN"}), key_ingredients_en=text)
    assert claim_check(p, "VEGETARIAN")[0] == TrustLevel.CONTRADICTED


@pytest.mark.parametrize("text", ["VETEMJÖL", "RÅGMJÖL", "DINKEL flour"])
def test_gluten_free_claim_is_contradicted_by_swedish_cereals(text):
    p = replace(BASE, claims=frozenset({"FREE_FROM_GLUTEN"}), key_ingredients_en=text)
    assert claim_check(p, "FREE_FROM_GLUTEN")[0] == TrustLevel.CONTRADICTED


def test_gluten_free_with_listed_oats_waits_for_a_person():
    p = replace(BASE, claims=frozenset({"FREE_FROM_GLUTEN"}), contains=frozenset({"GO"}))
    level, why = claim_check(p, "FREE_FROM_GLUTEN")
    assert level == TrustLevel.UNCHECKED and "oats" in why[0]


def test_plain_words_stay_clean():
    p = replace(BASE, claims=frozenset({"VEGETARIAN"}), key_ingredients_en="tomato, basil, mozzarella (milk)")
    assert claim_check(p, "VEGETARIAN")[0] == TrustLevel.CONSISTENT
