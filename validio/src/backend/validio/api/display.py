"""Text fields for the screens, added next to the raw values in the API views and never stored.

Every view keeps its numbers, ids and codes; these helpers only say them in words (validio.text.format)."""

import re
from datetime import date

from ..text.format import (
    and_list,
    cap,
    fact_text,
    money,
    product_qty,
    qty_text,
    short_name,
    short_names,
    short_ref,
    time_text,
)

# the Spend Pass fields under the names a person reads
PASS_FIELDS = {
    "autoLimitCents": "auto limit", "auto_limit_cents": "auto limit", "hardCapCents": "never above",
    "hard_cap_cents": "never above", "diet": "diet", "categories": "product groups", "deliverBy": "deliver by",
    "deliver_by": "deliver by", "substitutes": "substitutes", "split": "split limit",
    "split_max_extra_bp": "split limit", "splitMaxExtraBp": "split limit", "approvers": "approvers",
    "split_allow_listed": "substitutes in a split", "splitAllowListed": "substitutes in a split",
}
ACTORS = {"validio": "Validio", "presenter": "Demo", "demo": "Demo", "owner": "Owner"}
SUMMARY_WORDS = 14  # "about twelve": a quantity like "10 × 2.5 kg" counts as two


def product(pid: str | None):
    """The catalogue product, or None when no catalogue is open (a view built outside the app)."""
    if not pid:
        return None
    try:
        from .steady import runtime
        return runtime.catalog.get(pid)
    except Exception:  # noqa: BLE001  a missing catalogue only costs the size in the text
        return None


def qty(n, unit: str | None, pid: str | None) -> str | None:
    if n is None:
        return None
    p = product(pid)
    return product_qty(n, p, unit) if p is not None else qty_text(n, unit)


def pass_fields(keys: list[str]) -> list[str]:
    return [PASS_FIELDS.get(k, re.sub(r"(?<!^)(?=[A-Z])", " ", k).replace("_", " ").lower()) for k in keys]


def actor(a: str) -> str:
    if a in ACTORS:
        return ACTORS[a]
    if a.startswith("agent:"):
        return "Agent"
    if a.startswith("validio:"):
        return "Validio"
    if ":" in a:
        return cap(a.split(":")[-1])
    return a


def _words(s: str) -> int:
    return len([w for w in s.split() if w not in ("×", "x", "€", "%")])


def summary(sentence: str | None) -> str | None:
    """At most about twelve words for a list row: the first sentence, cut at a clause when it is longer.
    The full sentence stays next to it."""
    if not sentence:
        return None
    first = re.split(r"(?<=[.?!])\s+(?=[A-Z])", sentence.strip(), maxsplit=1)[0].rstrip(".")
    first = re.sub(r"\s*\([^)]*\)", "", first)
    if _words(first) <= SUMMARY_WORDS:
        return first + "."
    for cut in (" without ", ": ", ", ", " because ", " and "):
        head, sep, rest = first.partition(cut)
        if not sep:
            continue
        if cut == ": ":  # "Needs a person: a, b and c" keeps the first reason
            item = re.split(r", | and ", rest, maxsplit=1)[0]
            if _words(f"{head}: {item}") <= SUMMARY_WORDS:
                return f"{head}: {item}."
        if _words(head) <= SUMMARY_WORDS:
            return head + "."
    return " ".join(first.split()[:SUMMARY_WORDS]) + "."


def reasons(sentence: str | None) -> list[str]:
    """The sentence as its sentences, so a screen can show them as a list."""
    if not sentence:
        return []
    return [s for s in re.split(r"(?<=[.?!])\s+(?=[A-Z0-9])", sentence.strip()) if s]


def day_word(iso: str | None) -> str | None:
    """"2026-11-16" reads "Mon 16 Nov"."""
    if not iso:
        return None
    d = date.fromisoformat(iso[:10])
    return f"{d:%a} {d.day} {d:%b}"


def title(lines: list, deliver_by: str | None) -> str | None:
    """What the request asks for, from the parsed need: "1,000 litres of lactose-free milk by Mon 16 Nov"."""
    parts = []
    for ln in lines:
        need = ln.need
        if need.product_id:
            q = need.qty_text or ""
            parts.append(f"{q} of {short_ref(name_of(ln, need.product_id), with_size='×' not in q)}")
        else:
            what = " ".join([*(d.replace(" free", "-free") for d in need.diet), need.what])
            parts.append(f"{need.qty_text} of {what}")
    if not parts:
        return None
    head = parts[0] if len(parts) == 1 else f"{parts[0]} and {len(parts) - 1} more"
    by = day_word(deliver_by)
    return cap(head + (f" by {by}" if by else ""))


def name_of(ln, pid: str) -> str:
    for o in [*ln.options, *(ln.substitutes or []), *(ln.beyond_list or [])]:
        if o.product_id == pid:
            return o.name
    p = product(pid)
    return p.name_en if p is not None else pid


__all__ = [
    "actor",
    "and_list",
    "day_word",
    "fact_text",
    "money",
    "pass_fields",
    "product",
    "qty",
    "reasons",
    "short_name",
    "short_names",
    "summary",
    "time_text",
    "title",
]


# Turned-down options under one heading each. The first group whose pattern matches any reason wins, in
# this order: what a rule forbids first, then what Valio cannot deliver, then what does not fit the need.
GROUPS: tuple[tuple[str, str], ...] = (
    ("Over the hard cap", r"over the hard cap"),
    ("Breaks a Spend Pass rule", r"^Blocked:"),
    ("Not lactose free", r"not lactose free|no lactose-free claim"),
    ("Not gluten free", r"not gluten free|no gluten-free claim"),
    ("Not vegan", r"not vegan|no vegan claim"),
    ("Out of stock at Valio", r"Out of stock at Valio|^Only .* in stock"),
    ("No delivery date", r"no delivery date"),
    ("Order cut-off passed", r"cut-off .*has passed"),
    ("Not {what}", r", not ([a-z][a-z -]*?)\.?$"),
    ("Packs too small", r"too small for"),
    ("Pack size unknown", r"^Pack size unknown"),
    ("Quantity unknown", r"quantity is unknown"),
)
TURNED_DOWN = ("rejected", "blocked", "not_deliverable")
SHORT_WORDS = 8


def group(reasons: list[str]) -> tuple[str, int, str | None]:
    """The heading, its place in GROUPS and the reason that put it there."""
    for i, (head, pat) in enumerate(GROUPS):
        for r in reasons:
            m = re.search(pat, r.rstrip("."), re.IGNORECASE)
            if m:
                return head.format(what=m.group(1)) if "{what}" in head else head, i + 1, r
    return "Turned down", len(GROUPS) + 1, None


def short_text(verdict: str, reasons: list[str]) -> str | None:
    """At most about eight words for an option row; the reasons stay as they are."""
    if not reasons:
        return None
    if verdict in TURNED_DOWN:
        head, _, why = group(reasons)
        cap = re.search(r"([\d,.]+ €) is over the hard cap of ([\d,.]+ €)", why or "")
        if cap:
            return f"{cap.group(1)} is over the {cap.group(2)} hard cap."
        if why and _words(why) <= SHORT_WORDS:
            return why if why.endswith(".") else why + "."
        return head + "."
    text = " ".join(reasons)
    more = re.search(r"([\d,.]+ €) more than the cheapest", text)
    if more:
        return f"{more.group(1)} more."
    if "Cheapest safe option" in text:
        if "every time" in text:
            return "Cheapest safe option, always delivered in full."
        seen = re.search(r"as ordered (\d+) of (\d+) times", text)
        if seen:
            return f"Cheapest safe option, {round(100 * int(seen.group(1)) / int(seen.group(2)))} % delivered in full."
        return "Cheapest safe option."
    first = reasons[0]
    if _words(first) <= SHORT_WORDS:
        return first
    return " ".join(first.rstrip(".").split()[:SHORT_WORDS]) + " …"
