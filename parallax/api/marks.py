"""Marks between an anchor sentence and its match: numbers that differ and terms the judge named.

With a verdict, its `numbers` and `terms` are used (the judge read both sentences). Without one, numbers
are extracted from both texts and the ones that appear on only one side are paired by kind and size.
Equal numbers in another spelling (26 662, 26.662, 26,662) are never a mark.
"""

import math
import re
from dataclasses import dataclass

_SEP = "   .,"
_PCT = r"\s?%|\s(?:per\s?cent|percent|prozent|procent|prosenttia|protsenti|процент\w*)"
_NUM = re.compile(rf"(?<![\w.,])(\d{{1,3}}(?:[{_SEP}]\d{{3}})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)({_PCT})?(?![\w%])", re.I)
_GROUPED = re.compile(rf"^\d{{1,3}}(?:[{_SEP}]\d{{3}})+$")
MIN_PLAIN = 100  # small plain numbers are mostly days and ordinals


@dataclass(frozen=True)
class Number:
    raw: str
    value: float
    pct: bool

    @property
    def kind(self) -> str:
        if self.pct:
            return "pct"
        if self.raw.isdigit() and len(self.raw) == 4 and 1000 <= self.value <= 2100:
            return "year"
        return "plain"


def number_value(raw: str) -> tuple[float, bool] | None:
    raw = raw.strip()
    m = re.search(f"(?:{_PCT})$", raw, re.I)
    pct = bool(m)
    s = raw[: m.start()].strip() if m else raw
    if _GROUPED.match(s):
        s = re.sub(rf"[{_SEP}]", "", s)
    else:
        m = re.match(rf"^(\d{{1,3}}(?:[{_SEP}]\d{{3}})+)([.,]\d+)$", s)
        if m:
            s = re.sub(rf"[{_SEP}]", "", m.group(1)) + "." + m.group(2)[1:]
        else:
            s = s.replace(",", ".")
    try:
        return float(s), pct
    except ValueError:
        return None


def extract_numbers(text: str) -> list[Number]:
    out = []
    for m in _NUM.finditer(text or ""):
        raw = m.group(1) + (m.group(2) or "")
        v = number_value(raw)
        if v is not None:
            out.append(Number(raw=raw, value=v[0], pct=v[1]))
    return out


def _same(a: str, b: str) -> bool:
    va, vb = number_value(a), number_value(b)
    if va is not None and vb is not None:
        return va == vb
    return a.strip().lower() == b.strip().lower()


def _text_number_marks(this: str, other: str) -> list[dict]:
    a, b = extract_numbers(this), extract_numbers(other)
    values_a = {(n.value, n.pct) for n in a}
    values_b = {(n.value, n.pct) for n in b}

    def keep(n: Number, other_values) -> bool:
        if (n.value, n.pct) in other_values:
            return False
        return n.kind != "plain" or n.value >= MIN_PLAIN

    only_a = list({(n.value, n.pct): n for n in a if keep(n, values_b)}.values())
    only_b = list({(n.value, n.pct): n for n in b if keep(n, values_a)}.values())
    marks = []
    for na in only_a:
        pool = [nb for nb in only_b if nb.kind == na.kind]
        if not pool:
            continue
        best = min(pool, key=lambda nb: abs(math.log(max(nb.value, 1e-9) / max(na.value, 1e-9))))
        ratio = max(best.value, na.value) / max(min(best.value, na.value), 1e-9)
        if na.kind == "plain" and ratio >= 10:
            continue
        only_b.remove(best)
        marks.append({"kind": "number", "this": na.raw, "other": best.raw})
    return marks


def marks_for(this: str, other: str, verdict: dict | None) -> list[dict]:
    """Marks for one cell. `verdict` carries the judge's `numbers` and `terms` pairs, oriented this -> other."""
    if verdict is None:
        return _text_number_marks(this, other)
    marks = [{"kind": "number", "this": a, "other": b} for a, b in verdict.get("numbers") or [] if not _same(a, b)]
    marks += [
        {"kind": "term", "this": a, "other": b}
        for a, b in verdict.get("terms") or []
        if a.strip().lower() != b.strip().lower()
    ]
    return marks
