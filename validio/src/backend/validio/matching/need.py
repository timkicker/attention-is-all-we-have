"""Turn a request into a typed need and narrow the static catalog to a few candidates.

Nothing here makes a live call. Every product that drops out gets a reason a chef understands.
"""

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta

from ..catalog.model import Product
from ..catalog.store import Catalog
from ..text.format import and_list, qty_text
from ..trust.claims import claim_check
from ..trust.levels import TrustLevel
from ..valio.models import Quote

MAX_CANDIDATES = 12
AGREE = 0.05  # two pack size sources must agree within 5 %


@dataclass
class Need:
    kind: str  # milk, mozzarella, oat_drink
    quantity: float
    unit: str  # L, KG, PCS
    required_claims: set[str]
    excluded_claims: set[str]
    deliver_by: date
    budget_cents: int | None
    product_id: str | None = None  # fixes the product, for standing order lines and product requests
    text: str = ""
    # the part of required_claims that comes only from the kitchen's Spend Pass, not from the request's text:
    # a product without the claim in Valio's data stays a candidate (its grade is unchecked, so Cedar sends it to
    # a person); only a product whose own data breaks it (kitchen_break) is screened out
    kitchen_claims: set[str] = field(default_factory=set)
    # the pack a count of packs names, in kilos or litres: "10 packs of bananas 4.5 kg" is (4.5, "KG")
    pack: tuple[float, str] | None = None

    @property
    def strict_claims(self) -> set[str]:
        """The claims the request's own text asks for: a product without them is screened out."""
        return self.required_claims - self.kitchen_claims


@dataclass
class Ranked:
    product: Product
    sales_qty: int | None
    total_cents: int | None
    accepted: bool
    reasons: list[str] = field(default_factory=list)  # why it was rejected, empty when accepted
    notes: list[str] = field(default_factory=list)  # facts worth showing that do not reject
    facts: list = field(default_factory=list)
    why: list[str] = field(default_factory=list)  # Best Pick: one sentence per ranking key
    diet_open: list[str] = field(default_factory=list)  # kitchen diets Valio's data does not confirm, by name


@dataclass(frozen=True)
class Kind:
    words: tuple[str, ...]
    unit: str
    categories: tuple[str, ...] | None  # Valio categories that hold this kind, None means any
    net: tuple[str, ...]  # category prefixes searched, wider than categories so look-alikes show
    off: str | None = None  # names that match the word but are another product
    off_name: str | None = None  # what those are, when OFF_NAMES does not fit this kind
    # a catalogue word: the name must hold it as a word of its own, maybe plural ("bananas", not "bananaleaves")
    whole: bool = False


# flavours: a plain drink asked for, these are another product
FLAVOURS = (r"choco|cookie|vanilla|caramel|hazelnut|gingerbread|pumpkin|cardamom|strawberr|banana|coffee|ikaffe"
            r"|protein|soy|cooking")

KINDS = {
    "milk": Kind(("milk",), "L", ("10400",), ("10400", "10401"),
                 r"sour|ferment|curdl|coffee|caf[eè]|powder|pudding|condensed|acidofilus|vanilla|hyla|gefilus"
                 r"|cream|portion"),
    "mozzarella": Kind(("mozzarella",), "KG", None, ("",)),
    "oat_drink": Kind(("oat",), "L", ("10402",), ("10402",), FLAVOURS, "A flavoured oat drink"),
}

CLAIM_WORDS = {
    "FREE_FROM_LACTOSE": (r"lactose[- ]free", "LOW_LACTOSE", "lactose"),
    "FREE_FROM_GLUTEN": (r"gluten[- ]free", None, "gluten"),
    "VEGAN": (r"\bvegan\b", None, "vegan"),
}
CLAIM_NAMES = {"FREE_FROM_LACTOSE": "lactose free", "FREE_FROM_GLUTEN": "gluten free", "VEGAN": "vegan"}
OFF_NAMES = {"sour": "Sour milk", "ferment": "Fermented milk", "curdl": "Curdled milk", "coffee": "Coffee milk",
             "cafè": "Café milk", "cafe": "Café milk", "powder": "Milk powder", "pudding": "A pudding",
             "condensed": "Condensed milk", "acidofilus": "Sour milk", "vanilla": "Flavoured milk",
             "hyla": "Sour milk", "gefilus": "Sour milk", "cream": "Cream", "portion": "Portion packs"}
NEAR_MISS = {"LOW_LACTOSE": "Low lactose is not lactose free"}
# the allergen a diet rules out: listed with no claim for the diet, the product breaks it
ALLERGEN_NAMES = {"AM": "milk", "ML": "lactose", "AW": "gluten cereals", "UW": "wheat"}
CLAIM_ALLERGEN = {"FREE_FROM_LACTOSE": "AM", "FREE_FROM_GLUTEN": "AW"}

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
UNITS = {"l": "L", "litre": "L", "litres": "L", "liter": "L", "liters": "L", "kg": "KG", "kilos": "KG",
         "kilo": "KG", "pcs": "PCS", "pieces": "PCS", "bags": "PCS", "packs": "PCS", "cartons": "PCS",
         "carton": "PCS", "boxes": "PCS", "box": "PCS", "bottles": "PCS", "cans": "PCS", "packages": "PCS"}
# words around the product word in a request that are never the product
FILLER = frozenset(["of", "a", "an", "the", "some", "please", "for", "by", "and", "with", "in", "on", "to", "from", "order", "need", "we", "need", "i", "want"]
                   + WEEKDAYS + ["budget", "euro", "eur", "free", "lactose", "gluten", "vegan", "next", "this",
                                 "week", "monday's", "fresh", "bulk"])


# kinds the parser found in the catalogue, by word: the categories most of the products with that word sit in
GENERIC: dict[str, Kind] = {}
MAX_GENERIC = 2000
# where counting names goes wrong: most names with "cream" are ice cream, Valio files cream under 10401,
# and a plant blend or a powder there is not the cream a kitchen asks for
CREAM_OFF = r"alternative|blend|plant|vegetable|coconut|powder|spray"
HINTS = {w: Kind((w,), "L", None, ("10401",), CREAM_OFF, "A cream alternative or mix")
         for w in ("cream", "cooking cream", "whipping cream")}


def kind_of(name: str, unit: str = "PCS") -> Kind:
    """A known kind, a catalogue word the parser resolved, or any product whose name holds the word."""
    return KINDS.get(name) or GENERIC.get(name) or Kind((name,), unit, None, ("",))


def fold(name: str) -> str:
    """A name lowercased without accents, so "puree" finds "purée"."""
    return "".join(c for c in unicodedata.normalize("NFKD", (name or "").lower()) if not unicodedata.combining(c))


# a product word that only flavours or goes into another product: joined to another word ("strawberry-banana",
# "peach & banana", "with butter"), or in the name of something processed ("banana yoghurt", "apple juice",
# "tomato puree", baby food). Counting where a word is densest counts the products that are the thing itself.
PROCESSED = re.compile(
    r"g(?:h)?urt|\b(?:puree|juice|jam|marmalade|jelly|compote|smoothie|shake|drink|kefir|soup|sauce|salsa|syrup"
    r"|porridge|gruel|baby ?food|months?|mth|flavou?r(?:ed)?|chips?|crisps?|bars?|bites?|biscuits?|cookies?"
    r"|cakes?|pies?|muffins?|crackers?|concentrate|nectar|powder|tea|candy|dried|crushed|peeled|chopped|pickled"
    r"|passata|paste|ice cream|sorbet|beverage|lemonade|soda|cider|in (?:oil|brine|syrup|water|sauce)"
    r"|napkins?|soap|candles?|wipes?|towels?|bags?)\b")  # the last: a colour or a scent


def _joined(word: str) -> re.Pattern:
    w = re.escape(word)
    return re.compile(rf"[-&+/]\s*{w}|\b{w}[a-z]*\s*[-&+/]|\b(?:and|with) {w}|\b{w}[a-z]* and\b")


def as_itself(word: str, name: str) -> bool:
    """The name is the product the word names, not a product it only flavours or goes into. The word's own
    words do not count: "apple juice" is itself in "Apple juice 1 l"."""
    name = fold(name)
    return not PROCESSED.search(name.replace(word, " ")) and not _joined(word).search(name)


# Valio's fruit and vegetables: fresh produce is named by the word itself ("BANANA 4.5KG", "APPLE GOLDEN 13KG")
FRESH_PRODUCE = "174"


def _heads(word: str, name: str) -> bool:
    """The name starts with the word as a word of its own, maybe plural, after a count: "BANANA 4.5KG", not
    "BANANALEAVES" or "EGGPLANT"."""
    return re.match(rf"(?:\d+ ?x ?)?{re.escape(word)}(?:e?s)?\b", fold(name).strip()) is not None


def _generic(word: str, cat: Catalog) -> Kind | None:
    """Products whose name holds the word at a word start, kept to the top level categories where the word is
    densest, at least half the densest share: "butter" stays with the fats (32 of 200) and leaves the frozen
    bakery (44 of 1,000 and more, croissants with butter), "oat drink" stays a drink.

    Only the products that are the thing itself count when there are any (as_itself): "banana" is the fresh
    fruit (7 of 901 in fruit and vegetables), not the baby food purées that name it (7 of 54)."""
    rx = re.compile(rf"\b{re.escape(word)}")
    hits = [p for p in cat.search(text=word, limit=5000) if rx.search(fold(p.name_en))]
    if not hits:
        return None
    if word in HINTS:
        return HINTS[word]
    sizes = cat.group_sizes()

    def densest(ps: list[Product]) -> tuple[str, ...] | None:
        counts = Counter(p.category[:3] for p in ps)
        share = {c: n / max(sizes.get(c, n), 1) for c, n in counts.items() if n >= 2}
        if not share:
            return None
        top = max(share.values())
        return tuple(sorted(c for c, s in share.items() if 2 * s >= top))

    itself = [p for p in hits if as_itself(word, p.name_en)]
    # a produce word: Valio names at least two fresh products by the word ("BANANA KG GT/CR", "APPLE GOLDEN 13KG"),
    # and no other group names more of its products that way, so frozen, canned or flavoured ones stay out
    heads = Counter(p.category[:3] for p in itself if _heads(word, p.name_en))
    if heads[FRESH_PRODUCE] >= 2 and heads[FRESH_PRODUCE] >= max(
            (n for c, n in heads.items() if c != FRESH_PRODUCE), default=0):
        return Kind((word,), "PCS", None, (FRESH_PRODUCE,), whole=True)
    net = densest(itself) or densest(hits)
    if net is None:  # a word with one product per group: where most of them are
        net = (Counter(p.category[:3] for p in hits).most_common(1)[0][0],)
    return Kind((word,), "PCS", None, net, whole=True)


def _singular(w: str) -> list[str]:
    """"tomatoes" gives "tomato", "berries" "berry", "bananas" "banana"."""
    if w.endswith("ies"):
        return [w[:-3] + "y"]
    if w.endswith("oes"):
        return [w[:-2]]
    return [w[:-1]] if w.endswith("s") else []


def _product_word(t: str, cat: Catalog) -> str | None:
    """The first product the catalogue knows in the request, two words before one ("whipping cream", "ice
    cream"), singular first since it finds both: "30 cartons of vegan pancakes" gives "pancake"."""
    t = re.sub(r"budget.*$|\b20\d\d-\d\d-\d\d\b|lactose[- ]free|gluten[- ]free", " ", t)
    words = [w for w in re.findall(r"[a-zäöå]{3,}", t) if w not in FILLER and w not in UNITS]
    for i, w in enumerate(words):
        nxt = words[i + 1] if i + 1 < len(words) else None
        tries = [f"{w} {n}" for n in ((nxt[:-1], nxt) if nxt and nxt.endswith("s") else (nxt,)) if n]
        tries += [*_singular(w), w]  # the singular finds both
        for form in tries:
            if form in GENERIC:
                return form
            if kind := _generic(form, cat):
                if len(GENERIC) >= MAX_GENERIC:
                    GENERIC.pop(next(iter(GENERIC)))  # the oldest word goes: never grows without bound
                GENERIC[form] = kind
                return form
    return None


def starts_word(word: str, text: str) -> bool:
    """`word` at the start of a word in `text`: "oat" in "oat drink" or "oats", never in "goat" or "coated"."""
    return re.search(rf"\b{re.escape(word)}", text, re.IGNORECASE) is not None


# a number as people write it: 1000, 1,000, 1.000, 1 000 (thousands), 2.5 or 2,5 (decimals), 1,000.50
NUMBER = r"(?<![\d.,])(\d{1,3}(?:(?:[ \u00a0\u202f]|,(?=\d{3}(?!\d))|\.(?=\d{3}(?!\d)))\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)"


def number(s: str) -> float:
    """A written number. Spaces always group thousands. With both ',' and '.' the last one is the decimal mark.
    One kind of mark followed by exactly three digits groups thousands ("1,000 litres", "1.000 litres");
    otherwise it is the decimal mark ("2,5 kg", "1.5 l")."""
    s = re.sub(r"[ \u00a0\u202f]", "", s)
    if "," in s and "." in s:
        dec = max(s.rfind(","), s.rfind("."))
        return float(re.sub(r"[.,]", "", s[:dec]) + "." + s[dec + 1:])
    for mark in (",", "."):
        if mark in s:
            parts = s.split(mark)
            if len(parts) > 2 or len(parts[-1]) == 3:
                return float("".join(parts))
            return float(s.replace(mark, "."))
    return float(s)


def parse_need(text: str, today: date, cat: Catalog | None = None) -> Need:
    """Deterministic parser for the demo phrasing. The agent may send typed lines instead. With a catalogue,
    any product word it has products for is a kind ("20 kg of parmesan"), not only milk, mozzarella and oat."""
    t = text.lower()
    m = re.search(NUMBER + r"\s*(" + "|".join(sorted(UNITS, key=len, reverse=True)) + r")\b", t)
    if not m:
        raise ValueError(f"no quantity in {text!r}")
    quantity, unit = number(m.group(1)), UNITS[m.group(2)]
    if quantity <= 0:
        raise ValueError(f"the quantity in {text!r} is not more than zero")
    if quantity.is_integer():
        quantity = int(quantity)
    pack = None
    if unit == "PCS":  # "10 packs of bananas 4.5 kg": ten packs of 4.5 kg each
        rest = re.sub(r"budget.*$", "", t[m.end():])
        if s := re.search(NUMBER + r"\s*(kg|g|l|dl|cl|ml)\b", rest):
            size = number(s.group(1)) * {**_TO_KG, **_TO_L}[s.group(2)]
            pack = (size, "KG" if s.group(2) in _TO_KG else "L") if size > 0 else None
    kind = next((k for k in KINDS if any(starts_word(w, t) for w in KINDS[k].words)), None)
    if kind is None and cat is not None:
        kind = _product_word(t, cat)
    if kind is None:
        raise ValueError(f"no known product kind in {text!r}")
    required, excluded = set(), set()
    for claim, (pattern, near, _) in CLAIM_WORDS.items():
        if re.search(pattern, t):
            required.add(claim)
            if near:
                excluded.add(near)
    deliver_by = today + timedelta(days=2)
    if d := re.search(r"\b(20\d\d-\d\d-\d\d)\b", t):
        deliver_by = date.fromisoformat(d.group(1))
    else:
        for i, name in enumerate(WEEKDAYS):
            if re.search(rf"\bby {name}\b", t):
                deliver_by = today + timedelta(days=(i - today.weekday() - 1) % 7 + 1)
    budget = None
    if b := re.search(r"budget\s*(?:of\s*)?" + NUMBER + r"\s*(?:€|eur|euro)", t):
        budget = round(number(b.group(1)) * 100)
    return Need(kind, quantity, unit, required, excluded, deliver_by, budget, text=text, pack=pack)


def _per_sales_unit(p: Product) -> float | None:
    if p.sales_unit in p.units:
        return p.units[p.sales_unit]
    return 1.0 if p.sales_unit == p.base_unit else None


_VOL = re.compile(r"(\d+(?:[.,]\d+)?)\s*(ml|cl|dl|l)\b", re.IGNORECASE)
_WGT = re.compile(r"(\d+(?:[.,]\d+)?)\s*(kg|g)\b", re.IGNORECASE)
_TO_L = {"ml": 0.001, "cl": 0.01, "dl": 0.1, "l": 1.0}
_TO_KG = {"g": 0.001, "kg": 1.0}


def _name_measure(name: str, rx: re.Pattern, factor: dict[str, float]) -> float | None:
    m = rx.search(name or "")
    return float(m.group(1).replace(",", ".")) * factor[m.group(2).lower()] if m else None


def _agree(sources: dict[str, float | None]) -> tuple[float | None, str]:
    vals = {k: v for k, v in sources.items() if v}
    if not vals:
        return None, "unknown"
    lo, hi = min(vals.values()), max(vals.values())
    if hi / lo > 1 + AGREE:
        return None, "sources disagree: " + ", ".join(f"{k} {v:g}" for k, v in vals.items())
    return round(next(iter(vals.values())), 3), "from " + ", ".join(vals)


def litres_per_sales_unit(p: Product, q: Quote | None = None) -> tuple[float | None, str]:
    n = _per_sales_unit(p)
    return _agree({
        "volume field": p.base_volume_l * n if p.base_volume_l and n else None,
        "name": (v * n) if (v := _name_measure(p.name_en, _VOL, _TO_L)) and n else None,
        "comparison price": q.price_cents / q.comparison_price_cents
        if q and q.price_cents and q.comparison_price_cents and q.comparison_unit == "L" else None,
    })


def kg_per_sales_unit(p: Product, q: Quote | None = None) -> tuple[float | None, str]:
    n = _per_sales_unit(p)
    return _agree({
        "weight field": p.base_weight_kg * n if p.base_weight_kg and n else None,
        "name": (v * n) if (v := _name_measure(p.name_en, _WGT, _TO_KG)) and n else None,
        "comparison price": q.price_cents / q.comparison_price_cents
        if q and q.price_cents and q.comparison_price_cents and q.comparison_unit == "KG" else None,
    })


def amount_per_sales_unit(need: Need, p: Product, q: Quote | None = None) -> tuple[float | None, str]:
    if need.unit == "L":
        return litres_per_sales_unit(p, q)
    if need.unit == "KG":
        return kg_per_sales_unit(p, q)
    return 1.0, "pieces"


def _in_net(need: Need, p: Product) -> bool:
    kind = kind_of(need.kind, need.unit)
    name = (p.name_en or "").lower()
    if not any(w in name for w in kind.words) and not (kind.whole and any(w in fold(name) for w in kind.words)):
        return False
    if kind.whole and not any(re.search(rf"\b{re.escape(w)}(?:e?s)?\b", fold(name)) for w in kind.words):
        return False  # "banana" is not in "bananaleaves"
    if not any(p.category.startswith(c) for c in kind.net):
        return False
    for claim in need.strict_claims:
        _, near, word = CLAIM_WORDS.get(claim, (None, None, None))
        if not (claim in p.claims or (near and near in p.claims) or (word and word in name)):
            return False
    # a kitchen-wide diet leaves out only what Valio's data says breaks it, never what it is silent on
    return not any(kitchen_break(p, c) for c in need.kitchen_claims)


def kitchen_break(p: Product, claim: str) -> str | None:
    """Why the product breaks a diet of the kitchen's Spend Pass, from Valio's data alone: the claim check
    contradicts it, or it lists the allergen the diet rules out and makes no claim. None when the data confirms
    the diet or says nothing about it; Cedar sends the second to a person (dietUnchecked)."""
    level, why = claim_check(p, claim)
    name = CLAIM_NAMES.get(claim, claim.lower())
    if level == TrustLevel.CONTRADICTED:
        return f"Not {name}: {and_list(why)}"
    code = CLAIM_ALLERGEN.get(claim)
    if level == TrustLevel.MISSING and code and code in p.contains:
        return f"Lists {ALLERGEN_NAMES[code]} and has no {name.replace(' ', '-')} claim in Valio's data"
    return None


def static_reasons(need: Need, p: Product) -> list[str]:
    """Reasons from the static catalog alone, so they cost no live call."""
    kind = kind_of(need.kind, need.unit)
    name = (p.name_en or "").lower()
    reasons = []
    strict = need.strict_claims
    has_all = strict <= p.claims
    if kind.off and (m := re.search(kind.off, name)):
        what = kind.off_name or OFF_NAMES.get(m.group(0), f"A {m.group(0)} product")
        reasons.append(f"{what}, not plain {need.kind.replace('_', ' ')}")
    elif kind.categories and p.category not in kind.categories:
        claim = " and ".join(CLAIM_NAMES.get(c, c) for c in sorted(strict))
        prefix = f"{claim.capitalize()} but " if has_all and claim else ""
        what = "a cooking fat mix" if re.search(r"vegetable|fat|blend", name) else f"in Valio category {p.category}"
        reasons.append(f"{prefix}{what}, not {need.kind.replace('_', ' ')}")
    for claim in sorted(strict - p.claims):
        near = next((NEAR_MISS[c] for c in p.claims & need.excluded_claims if c in NEAR_MISS), None)
        reasons.append(near or f"No {CLAIM_NAMES.get(claim, claim)} claim in Valio's data")
    if not reasons:
        per, note = amount_per_sales_unit(need, p)
        piece = per / _per_sales_unit(p) if per and _per_sales_unit(p) else None
        if per is None:
            reasons.append(f"Pack size unknown ({note})")
        elif need.unit == "L" and need.quantity >= 100 and piece < 1:
            reasons.append(f"{piece:g} l packs, too small for {qty_text(need.quantity, 'L')}")
    return reasons


def _pack_fits(pack: tuple[float, str], p: Product) -> bool:
    size, unit = pack
    per = (kg_per_sales_unit if unit == "KG" else litres_per_sales_unit)(p)[0]
    return per is not None and abs(per - size) <= AGREE * size


def diet_open_count(need: Need, p: Product) -> int:
    """How many of the kitchen-wide diets Valio's data has no claim for."""
    return sum(claim_check(p, c)[0] == TrustLevel.MISSING for c in need.kitchen_claims)


def screen(need: Need, cat: Catalog, limit: int | None = MAX_CANDIDATES) -> tuple[list[Product], list[Ranked]]:
    """Candidates for the live check and the products that dropped out, each with its reasons.

    When more than `limit` products pass, those with a delivery record in Valio's file go first,
    then the biggest packs, so a bulk order needs few cartons.
    """
    if need.product_id:
        p = cat.get(need.product_id)
        return ([p] if p else []), []
    kind = kind_of(need.kind, need.unit)
    seen: dict[str, Product] = {}
    for prefix in kind.net:
        for w in kind.words:
            for p in cat.search(text=w, category_prefix=prefix or None, limit=5000):
                seen.setdefault(p.id, p)
    kept, dropped = [], []
    for p in seen.values():
        if not _in_net(need, p):
            continue
        if kind.off_name and kind.off and re.search(kind.off, (p.name_en or "").lower()):
            continue  # a flavoured drink or a cream blend is another product: not listed, not refused
        reasons = static_reasons(need, p)
        if reasons:
            dropped.append(Ranked(p, None, None, False, reasons))
        else:
            kept.append(p)
    if need.pack and (fits := [p for p in kept if _pack_fits(need.pack, p)]):
        # the request names its pack and Valio has it: the other packs drop out, said why
        size = qty_text(need.pack[0], need.pack[1])
        dropped += [Ranked(p, None, None, False, [f"Not the {size} pack asked for"]) for p in kept if p not in fits]
        kept = fits
    # products Valio's data does not confirm the kitchen's diet for come after those it does
    kept.sort(key=lambda p: (diet_open_count(need, p), p.reliability is None, -(p.reliability or 0),
                             -(amount_per_sales_unit(need, p)[0] or 0), p.id))
    return (kept if limit is None else kept[:limit]), dropped


def candidates(need: Need, cat: Catalog) -> list[Product]:
    return screen(need, cat)[0]
