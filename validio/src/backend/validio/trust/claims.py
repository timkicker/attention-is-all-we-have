"""Check a diet claim against the other fields of the same product.

The ingredient text is read only to find contradictions, so supplier text can lower trust, never raise it.
A claim the product does not make is MISSING, never safe.
"""

import re

from ..catalog.model import Product
from .levels import TrustLevel

LACTOSE_FREE_MAX_G = 0.01  # g per 100 g, our reading until a Valio mentor confirms it
GLUTEN_CODES = {"AW": "gluten cereals", "UW": "wheat", "NR": "rye", "GB": "barley", "GS": "spelt", "GK": "kamut"}
FISH_CODES = {"AF": "fish", "AC": "crustaceans", "UM": "molluscs"}
ANIMAL_CODES = {"AM": "milk", "AE": "egg", "ML": "lactose"}
# cereal words in English, Finnish and Swedish (Valio's key ingredients are English, some keep the local word)
GLUTEN_WORDS = r"\b(WHEAT|BARLEY|RYE|SPELT|VEHNÄ|OHRA|RUIS|VETE|KORN|RÅG|DINKEL)\w*"
# oats (GO) are a gluten cereal on an allergen list, but certified gluten-free oats are allowed in a gluten-free
# product: a gluten-free claim with oats listed is not contradicted, it waits for a person (unchecked)
OATS = "GO"
# A cereal word counts unless it is one of these known gluten-free ingredients, written out in full:
# "gluten-free wheat starch", "gluten-free barley malt extract", "gluten-free malt extract (barley)".
_GF = r"(?<![\w-])(?<!not )(?<!non-)(?<!non )gluten[- ]free\s+"
GLUTEN_FREE_BEFORE = (re.compile(_GF + r"$", re.IGNORECASE), re.compile(_GF + r"malt\s+extract\s*\(\s*$", re.IGNORECASE))
GLUTEN_FREE_AFTER = (re.compile(r"(wheat\s+st(ar|ra)ch|barley\s+malt\s+extract)\b", re.IGNORECASE),
                     re.compile(r"barley\s*\)", re.IGNORECASE))
MEAT_WORDS = re.compile(
    r"\b(pork|beef|veal|chicken|turkey|duck|lamb|mutton|venison|meat|bacon|ham|salami|chorizo|pepperoni|prosciutto"
    r"|lard|tallow|gelatine?|anchov(?:y|ies)|liha|sianliha|naudanliha|kana|broileri?|kalkkuna|pekoni|kinkku|liivate"
    r"|kött|fläsk|kyckling|gelatin)\b(?!-free)", re.IGNORECASE)
HONEY = re.compile(r"\bhoney\b", re.IGNORECASE)


def _contains(p: Product, codes: dict[str, str]) -> list[str]:
    return [f"lists {name} as contained" for c, name in codes.items() if c in p.contains]


def _gluten_words(text: str | None) -> list[str]:
    text = text or ""
    out = []
    for m in re.finditer(GLUTEN_WORDS, text, re.IGNORECASE):
        before, after = text[max(0, m.start() - 40):m.start()], text[m.start():]
        exempt = any(b.search(before) and a.match(after) for b, a in zip(GLUTEN_FREE_BEFORE, GLUTEN_FREE_AFTER,
                                                                            strict=True))
        if not exempt:
            out.append(f"key ingredients name {m.group(0)}")
    return out


def claim_check(p: Product, claim: str) -> tuple[TrustLevel, list[str]]:
    has = claim in p.claims
    if claim == "FREE_FROM_LACTOSE":
        bad = _contains(p, {"ML": "lactose"})
        if p.lacs_g is not None and p.lacs_g > LACTOSE_FREE_MAX_G:
            bad.append(f"lactose {p.lacs_g:g} g per 100 g")
        if bad:
            return TrustLevel.CONTRADICTED, bad
        if not has:
            return TrustLevel.MISSING, ["no lactose-free claim in Valio's data"]
        if p.lacs_g is None:
            return TrustLevel.UNCHECKED, ["claims lactose free but gives no lactose value"]
        return TrustLevel.CONSISTENT, [f"lactose {p.lacs_g:g} g per 100 g"]

    if claim == "FREE_FROM_GLUTEN":
        bad = _contains(p, GLUTEN_CODES) + _gluten_words(p.key_ingredients_en)
        bad += [f"may contain {name}" for c, name in GLUTEN_CODES.items() if c in p.may_contain]
        if bad:
            return TrustLevel.CONTRADICTED, bad
        if not has:
            return TrustLevel.MISSING, ["no gluten-free claim in Valio's data"]
        if not p.has_allergen_data:
            return TrustLevel.UNCHECKED, ["claims gluten free but has no allergen data"]
        if OATS in p.contains:
            return TrustLevel.UNCHECKED, ["claims gluten free and lists oats, safe only with gluten-free oats"]
        return TrustLevel.CONSISTENT, ["no gluten cereal listed"]

    if claim in ("VEGETARIAN", "VEGAN"):
        codes = FISH_CODES | (ANIMAL_CODES if claim == "VEGAN" else {})
        bad = _contains(p, codes)
        bad += [f"key ingredients name {m.group(0)}" for m in MEAT_WORDS.finditer(p.key_ingredients_en or "")]
        if claim == "VEGAN" and HONEY.search(p.key_ingredients_en or ""):
            bad.append("key ingredients name honey")
        if bad:
            return TrustLevel.CONTRADICTED, bad
        if not has:
            return TrustLevel.MISSING, [f"no {claim.lower()} claim in Valio's data"]
        if not p.has_allergen_data:
            return TrustLevel.UNCHECKED, [f"claims {claim.lower()} but has no allergen data"]
        return TrustLevel.CONSISTENT, ["no animal ingredient listed"]

    if not has:
        return TrustLevel.MISSING, [f"no {claim} claim in Valio's data"]
    return TrustLevel.UNCHECKED, ["nothing in the data to check it against"]
