"""The demo's left terminal pane: the agent's tool calls and Validio's answers, one readable block each."""

import json
import os
import sys
from typing import Any

from .buyer import Event
from .tools import SUPPLIER_TEXT


def _eur(cents: int | None) -> str:
    return "-" if cents is None else f"{cents // 100}.{cents % 100:02d} EUR"


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
    if isinstance(obj, dict):
        return sum(1 if SUPPLIER_TEXT.search(k) and v else _withheld(v) for k, v in obj.items())
    if isinstance(obj, list):
        return sum(_withheld(v) for v in obj)
    return 0


def _args(args: dict) -> str:
    return ", ".join(f"{k}={json.dumps(v, ensure_ascii=False)}" for k, v in args.items())


def _request(a: dict, st: Style) -> list[str]:
    lc = a.get("liveChecked") or {}
    head = f"request {a.get('requestId')}: status {a.get('status')}, "
    out = [head + f"checked {lc.get('ids')} products live in {lc.get('calls')} calls"]
    for i, line in enumerate(a.get("lines", []), 1):
        need = line.get("need", {})
        what = need.get("text") or f"{need.get('quantity')} {need.get('unit')} of {need.get('productId')}"
        out.append(f"  line {i}: {what}")
        ranked = line.get("ranked", [])
        ok = [r for r in ranked if r.get("accepted")]
        no = [r for r in ranked if not r.get("accepted")]
        for r in ok[:3]:
            out.append(f"  {st.ok('ok')} {r['productId']} {r.get('name', '')[:44]:<44} "
                       f"{r.get('salesQty')} {r.get('unit')}  {_eur(r.get('totalCents'))}")
            out.append(st.dim(f"       {'. '.join((r.get('why') or [])[:2])}"))
        for r in no[:3]:
            out.append(f"  {st.bad('no')} {r['productId']} {r.get('name', '')[:44]:<44} "
                       f"{'; '.join(r.get('why') or [])}")
        rest = len(ok[3:]) + len(no[3:])
        if rest:
            out.append(st.dim(f"     and {rest} more options"))
        sub = line.get("substitutes")
        if sub:
            out.append("  substitutes, Valio's list first:")
            for o in sub.get("listed", []) + sub.get("outside", [])[:3]:
                out.append(f"    {o['verdict']:<22} {o['productId']} {o['sentence']}")
            out.append(f"    {sub.get('sentence', '')}")
        d = line.get("decision") or {}
        if d:
            rules = ", ".join(d.get("ruleIds") or [])
            out.append(f"  decision: {d.get('outcome')} ({rules}) {d.get('sentence', '')}")
    return out


def _order(a: dict, st: Style) -> list[str]:
    out = [f"order {a.get('id')}: {a.get('state')}, {_eur(a.get('totalCents'))}"]
    for ln in a.get("lines", []):
        out.append(f"  {ln.get('quantity')} {ln.get('unit')} of {ln.get('productId')} {ln.get('name', '')[:46]}")
    if (a.get("decision") or {}).get("sentence"):
        out.append(f"  {a['decision']['sentence']}")
    return out


def _search(a: dict, st: Style) -> list[str]:
    return [f"{len(a.get('products', []))} products from the catalog, no live call"] + [
        f"  {p['id']} {p.get('name', '')[:60]}" for p in a.get("products", [])]


def render(e: Event, st: Style) -> str:
    if e.kind == "task":
        return st.agent("kitchen") + f"  {e.data}\n"
    if e.kind == "call":
        return st.agent(f"agent -> {e.name}") + f"  {_args(e.data)}"
    if e.kind == "final":
        return "\n" + st.agent("agent") + f"  {e.data}\n"
    a = e.data
    if "error" in a:
        body = [st.bad(f"error: {a['error']}")]
    elif e.name in ("request_supply", "get_request"):
        body = _request(a, st)
    elif e.name in ("confirm_order", "get_order"):
        body = _order(a, st)
    elif e.name == "search_products":
        body = _search(a, st)
    else:
        body = [json.dumps(a, ensure_ascii=False)[:400]]
    n = _withheld(a)
    if n:
        body.append(st.dim(f"  {n} supplier text fields withheld from the agent's model"))
    return st.validio(f"Validio <- {e.name}") + "\n" + "\n".join("  " + b for b in body) + "\n"


def printer(color: bool | None = None, out=sys.stdout):
    st = Style(out.isatty() and not os.environ.get("NO_COLOR") if color is None else color)
    return lambda e: print(render(e, st), file=out, flush=True)
