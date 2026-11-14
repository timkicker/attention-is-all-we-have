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
    "autoLimitCents": "orders alone up to", "auto_limit_cents": "orders alone up to", "hardCapCents": "never above",
    "hard_cap_cents": "never above", "diet": "diet", "categories": "product groups", "deliverBy": "deliver by",
    "deliver_by": "deliver by", "substitutes": "substitutes", "split": "split limit",
    "preferLabels": "preferred labels", "prefer_labels": "preferred labels",
    "split_max_extra_bp": "split limit", "splitMaxExtraBp": "split limit", "approvers": "who approves",
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
        return first if first.endswith("?") else first + "."
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
        return f"+{more.group(1)}"
    if "Cheapest safe option" in text:
        if "every time" in text:
            return "Cheapest, always delivered in full."
        seen = re.search(r"as ordered (\d+) of (\d+) times", text)
        if seen:
            return f"Cheapest, {round(100 * int(seen.group(1)) / int(seen.group(2)))} % delivered in full."
        return "Cheapest."
    first = reasons[0]
    if _words(first) <= SHORT_WORDS:
        return first
    return " ".join(first.rstrip(".").split()[:SHORT_WORDS]) + " …"


def swap_text(reasons: list[str], diet: list[str], deliver_by: str | None) -> str | None:
    """The chosen option is a swap: what kind of swap and when it comes, "Cheapest lactose-free swap,
    delivered by 16 Nov.". Every accepted option arrives by the need's date, the ranking turns down any other."""
    if not any("Cheapest safe option" in r for r in reasons):
        return None
    kind = " and ".join(w.replace(" ", "-") for w in diet) or "safe"
    return f"Cheapest {kind} swap."


SEES = (("limits", ("autoLimitCents", "auto_limit_cents", "hardCapCents", "hard_cap_cents")),
        ("diet rules", ("diet",)), ("who approves", ("approvers",)),
        ("preferred labels", ("preferLabels", "prefer_labels")))


def _sees(keys: list[str]) -> str:
    words = [w for w, ks in SEES if any(k in keys for k in ks)]
    if len(words) > 1 and words[1] == "diet rules" and words[0] == "limits":
        words = ["limits and diet rules", *words[2:]]
    return and_list([w if w == "who approves" or w.startswith("your") else f"your {w}" for w in words])


def sees_text(disclosed: list[str], hidden: list[str]) -> str:
    """One sentence for the Spend Pass card: "The agent sees your limits and diet rules, not who approves or
    your preferred labels." The plain claims (product groups, deliver by) are not named, the agent sees them too."""
    shown, kept = _sees(disclosed), _sees(hidden).replace(" and ", " or ")
    if not shown:
        return f"The agent does not see {kept}." if kept else "The agent sees only the plain rules."
    return f"The agent sees {shown}" + (f", not {kept}." if kept else ".")


CHECKED = ("attested", "attested_until", "consistent")
CHECK_WORDS = {"quantity": "Stock: {}", "price": "Price {}", "cutoff": "Order cut-off {}",
               "reliability": "Delivered in full in {}", "carbon": "Footprint {}", "label": "Label {}",
               "allergens": "Allergens: {}"}


CHECK_ORDER = ("price", "cutoff", "reliability")
CHECK_MAX = 5


def checks(facts, diet: list[str] | None = None) -> list[str]:
    """At most five facts Validio confirmed, in a fixed order: price, order cut-off, delivered in full, then
    the diet claims ("Free from lactose"). With `diet`, only the claims that diet asks for. Supplier text,
    unchecked claims, the footprint, labels and allergens stay out."""
    from ..matching.need import CLAIM_NAMES
    ok = [f for f in facts if f.grade in CHECKED and (f.value_text or f.value)]
    out = []
    for kind in CHECK_ORDER:
        for f in ok:
            if f.field == kind:
                out.append(CHECK_WORDS[kind].format(f.value_text or f.value))
    for f in ok:
        kind, _, code = f.field.partition(":")
        if kind == "claim" and (diet is None or CLAIM_NAMES.get(code) in diet):
            out.append(cap(str(f.value_text or f.value)))
    return out[:CHECK_MAX]


def asks_text(sentence: str | None) -> str | None:
    """Why a waiting request waits for you, for its inbox row: "Asks you: the swap is not on Valio's list."."""
    said = ledger_text("approval", "", sentence or "")
    if not said or not said.startswith("Asked you: "):
        return None
    return "Asks you: " + said[11:].replace("the substitute", "the swap")


def why_reasons(reasons: list[str], short: str | None) -> list[str]:
    """The reasons for the Why fold without the one the short text already says."""
    if not short:
        return list(reasons)
    s = short.rstrip(".")
    marks = []
    if s.startswith("+") and s.endswith(" €"):
        marks.append("more than the cheapest")
    if s.startswith("Cheapest"):
        marks.append("Cheapest safe option")
    if s.endswith(" hard cap"):
        marks.append("is over the hard cap")
    for i, r in enumerate(reasons):
        if r.rstrip(".") == s or any(m in r for m in marks):
            return reasons[:i] + reasons[i + 1:]
    return list(reasons)


def _first(sentence: str) -> str:
    return re.split(r"(?<=[.?!])\s+(?=[A-Z])", sentence.strip(), maxsplit=1)[0]


def _end(s: str) -> str:
    s = s.strip()
    return s if s.endswith((".", "?", "!")) else s + "."


def ledger_text(kind: str, actor_text: str | None, sentence: str, title: str | None = None,
                order_id: str | None = None) -> str:
    """One short sentence with a verb for a ledger row. The actor has its own column, so it is not repeated;
    an order id shows once; money reads "1,200.00 €". The raw sentence stays for the detail fold."""
    s = sentence.strip()
    if kind == "request":
        budget = re.search(r"budget (\d[\d,.]*) ?(?:euro|EUR|€)", s)
        what = title or re.sub(r"^The agent asked for |\.$", "", _first(s))
        return _end(f"Asked for {what}" + (f", budget {money(round(float(budget.group(1).replace(',', '')) * 100))}"
                                           if budget else ""))
    steady = re.match(r"Steady Order S-\d+, (.+?): (.+)$", s)
    if steady:
        what, rest = steady.groups()
        stop = re.match(r"Not renewed: ([^.]+)\.", rest)
        if stop:
            return f"Did not renew {what}: {stop.group(1)}."
        wait = re.match(r"Waits for you: ([^.]+)\.", rest)
        why = wait.group(1) if wait else _first(rest).rstrip(".")
        return f"Held {what} for you: {why[:1].lower()}{why[1:]}."
    asked = re.match(r"Spend Pass \S+ already placed ([\d,.]+ €), so this order of ([\d,.]+ €) counts as ([\d,.]+ €)\. "
                     r"Needs a person: (.+)$", s)
    if asked:
        _, this, total, why = asked.groups()
        over = re.match(r"[\d,.]+ € is over the auto limit of ([\d,.]+ €)", why)
        if over:
            return f"Asked you: {this} would take the week to {total}, past {over.group(1)}."
        return f"Asked you: {_first(why).rstrip('.')}."
    if s.startswith("Needs a person: "):
        return f"Asked you: {_first(s[16:]).rstrip('.')}."
    alone = re.match(r"May order it alone: ([\d,.]+ €) is inside the auto limit of ([\d,.]+ €)", s)
    if alone:
        return f"Cleared it to order alone: {alone.group(1)} is within {alone.group(2)}."
    alone = re.match(r"Ordered (.+? without asking you)\.", s)
    if alone and order_id:
        return f"Placed {order_id}: {alone.group(1)}."
    placed = re.match(r"Placed order (O-\d+): (.+?) after the \w+ \w+\.", s)
    if placed:
        return f"Placed {placed.group(1)}: {placed.group(2)}."
    if actor_text and s.startswith(actor_text + " "):
        s = s[len(actor_text) + 1:]
        s = s[:1].upper() + s[1:]
    first = _first(s)
    first = re.sub(r" for the demo\.$", ".", first)
    if _words(first) > 20:
        return summary(first) or first
    return _end(first)
