"""The demo's left terminal pane: the agent's tool calls and Validio's answers, one readable block each."""

import json
import os
import sys
from typing import Any

from ..api import display
from .buyer import Event
from .tools import SUPPLIER_TEXT, untrusted_record


def _eur(cents: int | None, text: str | None = None) -> str:
    """The amount as the web app shows it, "1,010.00 €": Validio's moneyText, or the same helper."""
    return text or ("-" if cents is None else display.money(cents))


def _name(o: dict) -> str:
    """The short name the web app shows, "Lactose-free semi-skimmed milk 1 l"."""
    return o.get("displayName") or o.get("shortName") or o.get("name", "")


def _qty(o: dict, n=None, text: str | None = None) -> str:
    """"1,000 × 1 l", "200 bags": Validio's qtyText, or the same helper on the raw count."""
    n = o.get("quantity") if n is None else n
    return text or o.get("qtyText") or display.qty(n, o.get("unit"), o.get("productId")) or ""


class Style:
    def __init__(self, color: bool):
        self.color = color

    def _c(self, code: str, s: str) -> str:
        return f"\033[{code}m{s}\033[0m" if self.color else s

    def agent(self, s): return self._c("36;1", s)  # noqa: E704
    def validio(self, s): return self._c("33;1", s)  # noqa: E704
    def ok(self, s): return self._c("32", s)  # noqa: E704
    def bad(self, s): return self._c("31", s)  # noqa: E704
    def dim(self, s): return self._c("2", s)  # noqa: E704


def _withheld(obj: Any) -> int:
    if untrusted_record(obj):
        return 1
    if isinstance(obj, dict):
        return sum(1 if SUPPLIER_TEXT.search(k) and v else _withheld(v) for k, v in obj.items())
    if isinstance(obj, list):
        return sum(_withheld(v) for v in obj)
    return 0


def _args(args: dict) -> str:
    return ", ".join(f"{k}={json.dumps(v, ensure_ascii=False)}" for k, v in args.items())


def _opt(o: dict, st: Style, indent: str = "  ") -> list[str]:
    good = o.get("verdict") in ("chosen", "ranked")
    mark = st.ok(f"{o.get('verdict', ''):<15}") if good else st.bad(f"{o.get('verdict', ''):<15}")
    amount = f"{_qty(o)}  {_eur(o.get('totalCents'), o.get('moneyText'))}" if o.get("totalCents") else ""
    return [f"{indent}{mark} {o['productId']} {_name(o)[:42]:<42} {amount}",
            st.dim(f"{indent}{'':15}  {o.get('sentence', '')}")]


def _request(a: dict, st: Style) -> list[str]:
    lc = a.get("liveChecked") or {}
    rid = a.get("requestId") or a.get("id")
    out = [f"request {rid}: {a.get('status')}, checked {lc.get('ids')} products live in {lc.get('calls')} calls"]
    for m in a.get("simulated") or []:
        out.append(st.dim(f"  simulated: {m.get('sentence')}"))
    for i, line in enumerate(a.get("lines", []), 1):
        out.append(f"  line {i}: {line.get('text', '')}")
        opts = line.get("options", [])
        for o in opts[:5]:
            out += _opt(o, st, "    ")
        if len(opts) > 5:
            out.append(st.dim(f"    and {len(opts) - 5} more options"))
        if line.get("substitutes"):
            out.append("    Valio's substitute list:")
            for o in line["substitutes"]:
                out += _opt(o, st, "      ")
        if line.get("beyondList"):
            out.append("    beyond Valio's list:")
            for o in line["beyondList"][:3]:
                out += _opt(o, st, "      ")
        if line.get("swapSentence"):
            out.append(f"    {line['swapSentence']}")
    d = a.get("decision") or {}
    if d:
        out.append(f"  decision: {d.get('outcome')} ({', '.join(d.get('ruleIds') or [])}) {d.get('sentence', '')}")
    if a.get("question"):
        out.append(f"  question to the owner: {a['question']}")
    return out


def _order(a: dict, st: Style) -> list[str]:
    out = [f"order {a.get('id')}: {a.get('state')}, {_eur(a.get('totalCents'), a.get('moneyText'))}"]
    for ln in a.get("lines", []):
        out.append(f"  {_qty(ln)} of {ln.get('productId')} {_name(ln)[:46]}")
    return out


def _search(a, st: Style) -> list[str]:
    items = a if isinstance(a, list) else a.get("products", [])
    return [f"{len(items)} products from the catalog, no live call"] + [
        f"  {p['id']} {p.get('name', '')[:60]}" for p in items]


def _steady(a: dict, st: Style) -> list[str]:
    when = display.time_text(a["renewedAt"]) if a.get("renewedAt") else "not yet"
    out = [f"steady order {a.get('id')} {a.get('name', '')} ({a.get('weekday')}), renewed {when}"]
    for ln in a.get("lines", []):
        res = ln.get("result", "")
        mark = st.ok(f"{res:<14}") if res in ("renewed", "split_renewed", "accepted") else st.bad(f"{res:<14}")
        qty = _qty(ln, ln.get("thisWeekQuantity", ln.get("usualQuantity")), ln.get("qtyText") or ln.get("usualQtyText"))
        order = f"  order {ln['orderId']}" if ln.get("orderId") else ""
        out.append(f"  {mark} {ln['productId']} {_name(ln)[:40]:<40} {qty}  "
                   f"{_eur(ln.get('totalCents'), ln.get('moneyText'))}{order}")
        out.append(st.dim(f"  {'':14} {ln.get('sentence', '')}"))
        for f in ln.get("flags") or []:
            if f.get("sentence") and f["sentence"] not in ln.get("sentence", ""):
                out.append(st.dim(f"  {'':14} flag {f.get('kind')}: {f['sentence']}"))
    waits = [ln for ln in a.get("lines", []) if ln.get("acceptLabel")]
    if waits:
        out.append("  waits for the owner: " + ", ".join(
            f"{ln['productId']} ({ln['acceptLabel']})" for ln in waits))
    return out


def render(e: Event, st: Style) -> str:
    if e.kind == "task":
        return st.agent("kitchen") + f"  {e.data}\n"
    if e.kind == "call":
        return st.agent(f"agent -> {e.name}") + f"  {_args(e.data)}"
    if e.kind == "final":
        return "\n" + st.agent("agent") + f"  {e.data}\n"
    a = e.data
    if isinstance(a, dict) and "error" in a:
        body = [st.bad(f"error: {a['error']}")]
    elif e.name in ("request_supply", "get_request"):
        body = _request(a, st)
    elif e.name in ("confirm_order", "get_order"):
        body = _order(a, st)
    elif e.name == "renew_steady_order":
        body = _steady(a, st)
    elif e.name == "search_products":
        body = _search(a, st)
    else:
        body = [json.dumps(a, ensure_ascii=False)[:400]]
    n = _withheld(a)
    if n:
        body.append(st.dim(f"  {n} supplier text fields withheld from the agent's model"))
    return st.validio(f"Validio <- {e.name}") + "\n" + "\n".join("  " + b for b in body) + "\n"


def printer(color: bool | None = None, out=None):
    out = out or sys.stdout
    st = Style(out.isatty() and not os.environ.get("NO_COLOR") if color is None else color)
    return lambda e: print(render(e, st), file=out, flush=True)
