"""Display text for every sentence a person reads: one money shape, counts with thousands separators,
Valio's unit codes in words, catalogue names without shouting or trademark signs.

Only the words change, never a number. The raw values (cents, the unit code, the catalogue name) stay in
the API next to the text made from them."""

import re

# Valio's sales unit codes in words, singular and plural. A code not listed here is shown as it is, in lower case.
UNIT_WORDS: dict[str, tuple[str, str]] = {
    "ST": ("pack", "packs"), "PAK": ("pack", "packs"), "BAG": ("bag", "bags"), "KI": ("carton", "cartons"),
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
