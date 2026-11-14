"""Display text for every sentence a person reads: one money shape, counts with thousands separators,
Valio's unit codes in words, catalogue names without shouting or trademark signs.

Only the words change, never a number. The raw values (cents, the unit code, the catalogue name) stay in
the API next to the text made from them."""

import re

# Valio's sales unit codes in words, singular and plural. A code not listed here is shown as it is, in lower case.
UNIT_WORDS: dict[str, tuple[str, str]] = {
    "ST": ("piece", "pieces"), "PAK": ("pack", "packs"), "BAG": ("bag", "bags"), "KI": ("carton", "cartons"),
    "KRT": ("carton", "cartons"), "BOT": ("bottle", "bottles"), "CS": ("case", "cases"),
    "PAL": ("pallet", "pallets"), "KAN": ("canister", "canisters"), "KG": ("kg", "kg"),
    "L": ("litre", "litres"), "PCS": ("piece", "pieces"),
}

_SIZE = re.compile(
    r"(?<![A-WYZa-wyzÄÖÅäöå\d.,_])(?:e(?=\d))?(\d+(?:[.,]\d+)?)\s?"  # a number, "e2,5" is Valio's estimated mark
    r"(kg|mg|g|ml|cl|dl|l|cm|mm|pcs)(x(?=\d))?(?![a-zäöå])",
    re.IGNORECASE)
_SHOUT = re.compile(r"(?<![A-Za-zÄÖÅäöå])[A-ZÄÖÅ]{4,}(?![A-Za-zÄÖÅäöå])")


def money(cents: int) -> str:
    sign, cents = ("-" if cents < 0 else ""), abs(int(cents))
    return f"{sign}{cents // 100:,}.{cents % 100:02d} €"


def count(n: float) -> str:
    if float(n) == int(n):
        return f"{int(n):,}"
    return f"{n:,.2f}".rstrip("0").rstrip(".")


def unit_word(code: str | None, n: float = 2) -> str:
    code = (code or "").upper()
    if code not in UNIT_WORDS:
        return code.lower()
    one, many = UNIT_WORDS[code]
    return one if n == 1 else many


def qty_text(n: float, code: str | None) -> str:
    word = unit_word(code, n)
    return f"{count(n)} {word}" if word else count(n)


# units that are one item each: a quantity of them reads as "10 × 2.5 kg" when the catalogue gives the size
PIECE_UNITS = frozenset({"ST", "PCS"})


def _amount(x: float, small: str, big: str) -> str:
    return f"{count(round(x * 1000, 3))} {small}" if x < 1 else f"{count(round(x, 3))} {big}"


def size_text(p) -> str | None:
    """What one sales unit holds, from the catalogue's volume or weight per base unit: "2.5 kg", "1 l", "200 g".
    None when Valio gives neither."""
    if p is None:
        return None
    per = (p.units or {}).get(p.sales_unit, 1.0) if p.sales_unit != p.base_unit else 1.0
    if p.base_volume_l:
        return _amount(p.base_volume_l * per, "ml", "l")
    if p.base_weight_kg:
        return _amount(p.base_weight_kg * per, "g", "kg")
    if p.sales_unit == p.base_unit and (m := _SIZE_TOKEN.search(display_name(getattr(p, "name_en", "")))):
        return m.group(0) if "x" not in m.group(0) else None  # the size Valio writes in the name: "125 g"
    return None


def product_qty(n: float, p, unit: str | None = None) -> str:
    """A quantity of one product in the words a person reads everywhere: the catalogue's sales unit ("200 bags",
    "27 cartons"), or count × size for single items ("10 × 2.5 kg"). `unit` PCS means sales units; L and KG stay."""
    sales = p.sales_unit if p is not None else None
    code = (unit or sales or "").upper()
    if code == "PCS" and sales:
        code = sales.upper()
    if p is not None and code == (sales or "").upper() and code in PIECE_UNITS and (size := size_text(p)):
        return f"{count(n)} × {size}"
    return qty_text(n, code)


def _size(m: re.Match) -> str:
    num = m.group(1).replace(",", ".")
    if "." in num:
        num = num.rstrip("0").rstrip(".")
    return f"{num} {m.group(2).lower()}" + (" x " if m.group(3) else "")


def display_name(name: str | None) -> str:
    """The catalogue name as a person reads it: no ®/™, words in capitals title-cased (short acronyms like
    PDO or LED stay), a space before units and a decimal point ("e2,5 kg" becomes "2.5 kg")."""
    if not name:
        return ""
    s = re.sub(r"[®™©]", "", name)
    s = _SHOUT.sub(lambda m: m.group(0).capitalize(), s)
    s = _SIZE.sub(_size, s)
    return re.sub(r"\s+", " ", s).strip()


def and_list(items: list[str]) -> str:
    """"a", "a and b", "a, b and c". No comma before the "and"."""
    items = [i for i in items if i]
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1] if items else ""


def sentences(parts: list[str]) -> str:
    """Fragments as whole sentences: each starts with a capital and ends with a period, none is repeated."""
    out: list[str] = []
    for p in parts:
        p = (p or "").strip().rstrip(".;")
        if p and (s := p[0].upper() + p[1:] + ("" if p.endswith(("?", "!")) else ".")) not in out:
            out.append(s)
    return " ".join(out)


# Short names: at most about five words a person reads at a glance. Brands and Valio's codes go, the size stays.
_BRANDS = frozenset(["valio", "castelli", "gran", "arla", "pro", "lagerblad", "foods", "findus", "galbani", "topfoods", "maestrella", "hyvä", "suomalainen", "arki", "eila", "luomu", "gefilus", "hyla"])
_NOISE = frozenset(["uht", "esl", "pdo", "suomi", "suomesta", "fried", "frozen", "ca", "drink", "novobox", "based", "on", "mix", "from"])
_FRONT = ("organic", "vegan", "sliced")  # "mozzarella stange sliced" reads "sliced mozzarella stange"
_PACK = re.compile(r"^(\d+)\s?x\s?(?=\D)", re.IGNORECASE)
_SIZE_TOKEN = re.compile(r"(\d+\s?x\s?)?\d+(?:\.\d+)? (?:kg|g|l|dl|cl|ml)\b")


def _short_parts(name: str | None, with_size: bool = True) -> tuple[str, str]:
    """(short name, brand words it left out)."""
    s = display_name(name)
    pack = ""
    if m := _PACK.match(s):
        pack, s = m.group(1), s[m.end():]
    size = ""
    if m := _SIZE_TOKEN.search(s):
        size = re.sub(r"\s?x\s?", " x ", m.group(0))
    s = _SIZE_TOKEN.sub(" ", s)
    s = re.sub(r"\d+(?:[.,]\d+)?\s?%|[/,()]", " ", s)
    lactose = ""
    for phrase, word in (("lactose free", "lactose-free"), ("low lactose", "low-lactose")):
        if re.search(phrase, s, re.IGNORECASE):
            lactose, s = word, re.sub(phrase, " ", s, flags=re.IGNORECASE)
    brand, front, core = [], [], []
    for w in s.split():
        lw = w.lower()
        if lw in _BRANDS:
            brand.append(w)
        elif lw in _FRONT:
            front.append(lw)
        elif lw not in _NOISE and lw not in (c.lower() for c in core):
            core.append(w if (w.isupper() and len(w) <= 3) else lw)
    text = " ".join([lactose, *front, " ".join(core[:4])]).replace("semi skimmed", "semi-skimmed").strip()
    text = re.sub(r"\s+", " ", text)
    if not core:
        return display_name(name), ""
    if size and with_size:
        text += " " + (f"{pack} × {size}" if pack else size)
    elif pack and with_size:
        text = f"{pack} × {text}"
    return (text[:1].upper() + text[1:]) if text else display_name(name), " ".join(brand)


def short_name(name: str | None) -> str:
    """"Gran Castelli mozzarella 125g lactose free" reads "Lactose-free mozzarella 125 g"."""
    return _short_parts(name)[0]


def short_names(names: list[str]) -> list[str]:
    """Short names for products shown together. Where two would read the same, one brand word comes back (the
    last one the others do not share: "Arki lactose-free semi-skimmed milk 1 l"), and where even that does not
    tell them apart, the full name."""
    parts = [_short_parts(n) for n in names]
    plain = [p[0] for p in parts]
    out = list(plain)
    for test in (any, all):  # first a word no rival has, then one not every rival has
        for i, (s, b) in enumerate(parts):
            rivals = [parts[j][1].lower().split() for j in range(len(parts)) if j != i and plain[j] == s]
            if not rivals or out[i] != s or out.count(s) == 1:
                continue
            own = [w for w in b.split() if not test(w.lower() in r for r in rivals)]
            if own:
                out[i] = f"{own[-1]} {s[:1].lower()}{s[1:]}"
    for i, s in enumerate(out):
        if out.count(s) > 1:  # a word only this name has, such as "UHT", tells it apart without the whole name
            rivals = [names[j].lower() for j in range(len(out)) if j != i and out[j] == s]
            own = [w for w in re.findall(r"[A-Za-z]{3,}", names[i]) if not any(w.lower() in r for r in rivals)
                   and w.lower() not in s.lower()]
            out[i] = f"{s} {own[0]}" if own else display_name(names[i])
    for i, s in enumerate(out):
        if out.count(s) > 1:
            out[i] = display_name(names[i])
    return out


# GS1 allergen type codes as Valio sends them, in words. A code not listed is named as a code, never guessed.
ALLERGEN_WORDS = {
    "AM": "milk", "ML": "lactose", "AW": "gluten cereals", "UW": "wheat", "AY": "soy", "AE": "eggs",
    "AN": "tree nuts", "AP": "peanuts", "AS": "sesame", "AF": "fish", "AC": "crustaceans", "UM": "molluscs",
    "BC": "celery", "BM": "mustard", "AU": "sulphites", "NL": "lupin", "GB": "barley", "GO": "oats", "NR": "rye",
    "GS": "spelt", "GK": "kamut", "SA": "almonds", "SH": "hazelnuts", "SW": "walnuts", "SC": "cashews",
    "SP": "pecans", "SR": "brazil nuts", "ST": "pistachios", "SM": "macadamia nuts",
}


def allergen_words(codes) -> str:
    return and_list([ALLERGEN_WORDS.get(c, f"allergen code {c}") for c in codes])


def day_text(iso: str) -> str:
    """"2026-12-31" reads "31 Dec 2026"."""
    from datetime import date
    d = date.fromisoformat(iso[:10])
    return f"{d.day} {d:%b %Y}"


def time_text(iso: str | None) -> str | None:
    """A timestamp as a person reads it in a list: "10:00", no seconds."""
    if not iso:
        return None
    from datetime import datetime
    return f"{datetime.fromisoformat(iso):%H:%M}"


def _tidy(note: str) -> str:
    return re.sub(r"\s*;\s*", ", ", note)


def fact_text(field: str, value, note: str | None) -> tuple[str | None, str | None]:
    """(value, note) of one Fact for display: no placeholder counts, no unit codes, no ratios, no raw codes."""
    v = None if value is None else str(value)
    n = note
    if field == "quantity":
        if n and "placeholder" in n:
            v = "Valio gives no real count"
            n = "Valio gives no real count, treated as in stock" if "treated as in stock" in n \
                else "Valio gives no real count, not treated as stock"
        elif n and "sit at the supplier" in n:
            v, n = "Valio does not confirm its stock", "The goods sit at the supplier"
        elif v and (m := re.fullmatch(r"(-?\d+(?:\.\d+)?) ([A-Z]+)", v)):
            v = qty_text(float(m.group(1)), m.group(2))
    elif field == "reliability" and v is not None:
        try:
            v = f"{count(round(float(v) * 100, 1))} % of orders"
        except ValueError:
            pass
    elif field == "allergens" and v and v != "none contained":
        v = allergen_words([c.strip() for c in v.split(",")])
    elif field == "cutoff" and v:
        from datetime import datetime
        t = datetime.fromisoformat(v)
        v = f"{t.day} {t:%b %H:%M}"
    elif field.startswith("claim:") and v and re.fullmatch(r"[A-Z_]+", v):
        v = v.replace("_", " ").lower()  # FREE_FROM_LACTOSE reads "free from lactose"
    if field == "price" and n and (m := re.fullmatch(r"until (\d{4}-\d\d-\d\d)", n)):
        n = f"until {day_text(m.group(1))}"
    elif field == "price" and n:
        n = re.sub(r"^catalog price,\s*", "", n)  # the screens say "Valio price" already: no "price" twice
    return v, (_tidy(n) if n else n)


def short_ref(name: str | None, with_size: bool = True) -> str:
    """The short name inside a sentence: "of lactose-free mozzarella 125 g". A leading acronym keeps its capitals."""
    s = _short_parts(name, with_size)[0]
    first = s.split(" ", 1)[0]
    if (first.isupper() and len(first) <= 3) or s == display_name(name):  # an acronym, or the full name kept
        return s
    return s[:1].lower() + s[1:]


def cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def qty_of(n: float, p, unit: str | None = None, name: str | None = None) -> str:
    """"200 bags of lactose-free mozzarella 125 g", "10 × 2.5 kg of mozzarella-fontal crumbled cheese": the size
    is said once, in the quantity when it is there."""
    q = product_qty(n, p, unit)
    return f"{q} of {short_ref(name or (p.name_en if p is not None else ''), with_size='×' not in q)}"
