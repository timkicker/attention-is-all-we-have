"""Stand-in MCP server with the five tools, until lane B2's `validio.api.mcp_server` lands on main.

Every answer is computed by the real code on the recorded Valio answers: need matching, Best Pick,
Safe Swap, Hard Lines and the order service. It skips the Spend Pass check (it trusts the demo pass
M-1 with budget, hard cap and diet shown), so it is for the demo pane only, never for the API."""

import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

from ..audit.log import AuditLog
from ..catalog.store import Catalog
from ..config import load_settings
from ..demo.seed import NOW, apply_stockout
from ..matching.need import KINDS, Need, candidates, parse_need
from ..matching.rank import rank
from ..matching.substitute import safe_swap
from ..orders.service import OUTCOME, LineIn, OrderService
from ..orders.store import Store
from ..policy.decide import context_for, decide
from ..policy.mandate import Mandate
from ..valio.budget import CallBudget
from ..valio.client import ValioClient

DEMO_PASS = Mandate(
    id="M-1", issuer="kitchen:hotel-espoo", holder="agent:buyer-1", not_before=1794643200,
    expires=1794866400, categories=("104", "106", "418"), deliver_by="2026-11-16",
    substitutes="listed_and_rules_kept", split_max_extra_bp=500, split_allow_listed=True,
    auto_limit_cents=120000, hard_cap_cents=200000, diet=("FREE_FROM_LACTOSE",), prefer_labels=(),
    disclosed={"autoLimitCents": 120000, "hardCapCents": 200000, "diet": ["FREE_FROM_LACTOSE"]},
)
STATUS = {"auto_order": "allowed", "ask_human": "ask", "block": "blocked"}


def _option(r) -> dict[str, Any]:
    p = r.product
    return {"productId": p.id, "name": p.name_en, "salesQty": r.sales_qty, "unit": p.sales_unit,
            "totalCents": r.total_cents, "accepted": r.accepted, "why": r.why or r.reasons,
            "notes": r.notes, "descriptionUntrusted": p.planted_en or p.marketing_en}


def build(stockout: bool = False, now: datetime = NOW, workdir: Path | None = None) -> MCPServer:
    s = load_settings()
    cat = Catalog(s.catalog_db)
    valio = ValioClient(s.valio_base_url, "", "replay", s.valio_cache)
    work = Path(workdir or tempfile.mkdtemp(prefix="validio-pane-"))
    orders = OrderService(Store(work / "orders.db"), cat, valio, AuditLog(work / "ledger.db"), clock=lambda: now,
                          adjust=lambda a: apply_stockout(a, stockout))
    requests: dict[str, dict] = {}
    server = MCPServer("validio-standin")

    def need_for(line: dict, deliver_by: date) -> Need:
        if line.get("text"):
            n = parse_need(line["text"], now.date())
            n.deliver_by = deliver_by
            return n
        p = cat.get(line["productId"])
        kind = next((k for k, v in KINDS.items() if any(w in p.name_en.lower() for w in v.words)), "item")
        claims = {c for c in p.claims if c in DEMO_PASS.diet}
        return Need(kind, line["quantity"], "PCS", claims, set(), deliver_by, None, product_id=p.id)

    def one_line(line: dict, deliver_by: date, budget: CallBudget) -> dict:
        need = need_for(line, deliver_by)
        cands = candidates(need, cat)
        ids = [p.id for p in cands]
        q, a = valio.price(ids, deliver_by, budget), apply_stockout(valio.availability(ids, deliver_by, budget),
                                                                    stockout)
        ranked = rank(need, cands, q, a, now)
        out: dict[str, Any] = {"need": line, "ranked": [_option(r) for r in ranked]}
        top = ranked[0] if ranked and ranked[0].accepted else None
        if top:
            chosen = {"productId": top.product.id, "salesQty": top.sales_qty}
            ctx = context_for(DEMO_PASS, top.product, a.get(top.product.id), total_cents=top.total_cents,
                              now=now, required_claims=need.required_claims)
        else:
            swap = safe_swap(cat.get(ids[0]), need, cat, valio, deliver_by, budget, now)
            out["substitutes"] = {
                "listed": [{"productId": o.product.id, "name": o.product.name_en, "verdict": str(o.verdict),
                            "sentence": o.sentence} for o in swap.listed],
                "outside": [{"productId": o.product.id, "name": o.product.name_en, "verdict": str(o.verdict),
                             "sentence": o.sentence} for o in swap.outside],
                "sentence": swap.sentence,
            }
            if swap.best is None:
                out["decision"] = {"outcome": "block", "ruleIds": [], "sentence": swap.sentence}
                return out
            b = swap.best
            chosen = {"productId": b.product.id, "salesQty": b.ranked.sales_qty, "isSubstitute": True,
                      "onValioList": b.on_valio_list}
            sa = valio.availability([b.product.id], deliver_by, budget)[b.product.id]
            ctx = context_for(DEMO_PASS, b.product, sa, total_cents=b.ranked.total_cents, now=now,
                              is_substitute=True, on_valio_list=b.on_valio_list,
                              required_claims=need.required_claims)
        d = decide(ctx, chosen["productId"])
        out["chosen"] = chosen
        out["decision"] = {"outcome": OUTCOME[d.outcome], "ruleIds": d.rule_ids, "sentence": d.sentence}
        return out

    @server.tool()
    def search_products(text: str, category: str | None = None, claims: list[str] | None = None,
                        limit: int = 10) -> dict:
        """Search Valio's catalog. Static data only, no live call."""
        hits = cat.search(text=text, category_prefix=category, claims=set(claims or ()), limit=min(limit, 20))
        return {"products": [{"id": p.id, "name": p.name_en, "category": p.category, "salesUnit": p.sales_unit,
                              "claims": sorted(p.claims), "labels": sorted(p.labels),
                              "descriptionUntrusted": p.planted_en or p.marketing_en} for p in hits]}

    @server.tool()
    def request_supply(lines: list[dict], deliverBy: str, idempotencyKey: str, spendPass: str | None = None) -> dict:
        """Ask Validio for supplies."""
        rid = f"R-{len(requests) + 1}"
        budget = CallBudget(s.valio_max_ids)
        out = [one_line(ln, date.fromisoformat(deliverBy), budget) for ln in lines]
        worst = max((ln["decision"]["outcome"] for ln in out), key=["auto_order", "ask_human", "block"].index)
        res = {"requestId": rid, "status": STATUS[worst], "deliverBy": deliverBy, "lines": out,
               "liveChecked": {"calls": budget.calls, "ids": budget.ids_sent}}
        requests[rid] = res
        return res

    @server.tool()
    def get_request(requestId: str) -> dict:
        """Read a request result again."""
        return requests[requestId]

    @server.tool()
    def confirm_order(requestId: str, choice: list[dict], idempotencyKey: str, spendPass: str | None = None) -> dict:
        """Confirm the chosen products. Validio prices everything again."""
        req = requests[requestId]
        lines = [LineIn(c["productId"], int(c["salesQty"]), bool(c.get("isSubstitute")),
                        bool(c.get("onValioList"))) for c in choice]
        o = orders.submit(mandate=DEMO_PASS, lines=lines, deliver_by=date.fromisoformat(req["deliverBy"]),
                          idempotency_key=idempotencyKey, request_id=requestId)
        return {k: o[k] for k in ("id", "requestId", "state", "totalCents", "lines", "decision") if k in o}

    @server.tool()
    def get_order(orderId: str) -> dict:
        """Read an order and its state."""
        o = orders.get(orderId)
        return {k: o[k] for k in ("id", "requestId", "state", "totalCents", "history") if k in o}

    return server
