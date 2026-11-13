"""The web app's API under /api. Approve needs the 6 digit code when VALIDIO_APPROVE_CODE is set,
the demo switches need VALIDIO_DEMO=1 and the X-Demo-Token header when VALIDIO_DEMO_TOKEN is set."""

import hmac
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Header, HTTPException

from ..matching.need import CLAIM_NAMES
from ..policy.mandate import DEMO_SD_FIELDS
from .schemas import (
    ApproveIn,
    DemoState,
    InboxItem,
    LedgerView,
    OrderView,
    SpendPassView,
    SupplyRequestView,
)
from .state import MAX_CODE_TRIES, Ctx, get_ctx
from .tools import get_order, get_request

router = APIRouter(prefix="/api", tags=["web"])
CtxDep = Annotated[Ctx, Depends(get_ctx)]
HELSINKI = timezone(timedelta(hours=2))


def _code(ctx: Ctx, order_id: str, header: str | None, body: ApproveIn | None) -> None:
    if not ctx.approve_code:
        return
    if ctx.code_tries.get(order_id, 0) >= MAX_CODE_TRIES:
        raise HTTPException(429, "too many wrong codes for this order")
    given = header or (body.code if body else None) or ""
    if not hmac.compare_digest(given.encode(), ctx.approve_code.encode()):
        ctx.code_tries[order_id] = ctx.code_tries.get(order_id, 0) + 1
        raise HTTPException(403, "wrong or missing approval code")


def _demo(ctx: Ctx, token: str | None) -> None:
    if not ctx.settings.demo:
        raise HTTPException(404, "demo controls are off")
    if ctx.demo_token and not hmac.compare_digest((token or "").encode(), ctx.demo_token.encode()):
        raise HTTPException(403, "wrong or missing demo token")


@router.get("/inbox", response_model=list[InboxItem], response_model_exclude_none=True)
def inbox(ctx: CtxDep):
    out = []
    for r in reversed(ctx.store.requests()):
        v = get_request(ctx, r["id"])
        sentence = v.question if v.status == "waiting" and v.question else (v.decision.sentence if v.decision else "")
        out.append(InboxItem(id=v.id, created_at=v.created_at, text=v.text, status=v.status, sentence=sentence,
                             total_cents=v.total_cents))
    return out


@router.get("/requests/{request_id}", response_model=SupplyRequestView, response_model_exclude_none=True)
def request_detail(ctx: CtxDep, request_id: str):
    return get_request(ctx, request_id)


@router.get("/spend-passes/{pass_id}", response_model=SpendPassView, response_model_exclude_none=True)
def spend_pass(ctx: CtxDep, pass_id: str):
    """The Spend Pass as the agent last showed it. Fields it did not disclose stay absent."""
    m = ctx.store.seen_pass(pass_id)
    if m is None:
        raise HTTPException(404, f"no agent has shown Spend Pass {pass_id} yet")
    shown = sorted(m["disclosed"])
    return SpendPassView(
        id=m["id"], issuer=m["issuer"], holder=m["holder"],
        valid_from=datetime.fromtimestamp(m["not_before"], HELSINKI).isoformat(),
        valid_to=datetime.fromtimestamp(m["expires"], HELSINKI).isoformat(),
        auto_limit_cents=m["auto_limit_cents"], hard_cap_cents=m["hard_cap_cents"],
        diet=[CLAIM_NAMES.get(d, d) for d in m["diet"]] if m["diet"] is not None else None,
        categories=m["categories"], deliver_by=m["deliver_by"], substitutes=m["substitutes"],
        split={"max_extra_cost_pct": m["split_max_extra_bp"] / 100, "allow_listed_substitutes": m["split_allow_listed"]},
        disclosed=shown, hidden=sorted(DEMO_SD_FIELDS - set(shown)),
    )


@router.get("/orders/{order_id}", response_model=OrderView, response_model_exclude_none=True)
def order(ctx: CtxDep, order_id: str):
    return get_order(ctx, order_id)


@router.post("/orders/{order_id}/approve", response_model=OrderView, response_model_exclude_none=True)
def approve(ctx: CtxDep, order_id: str, body: Annotated[ApproveIn | None, Body()] = None,
            x_approve_code: Annotated[str | None, Header()] = None):
    """Approve a waiting order. Validio asks Valio again and refuses if a price rose more than 2 %
    or a line can no longer be delivered. A placed order cannot be approved twice."""
    _code(ctx, order_id, x_approve_code, body)
    return OrderView.model_validate(ctx.orders.approve(order_id, approver="owner"))


@router.post("/orders/{order_id}/reject", response_model=OrderView, response_model_exclude_none=True)
def reject(ctx: CtxDep, order_id: str, body: Annotated[ApproveIn | None, Body()] = None,
           x_approve_code: Annotated[str | None, Header()] = None):
    _code(ctx, order_id, x_approve_code, body)
    return OrderView.model_validate(ctx.orders.reject(order_id, approver="owner"))


@router.get("/ledger", response_model=LedgerView, response_model_exclude_none=True)
def ledger(ctx: CtxDep):
    ok, count, broken_at = ctx.audit.verify()
    entries = [{"seq": e.seq, "at": e.at, "actor": e.actor, "kind": e.kind, "sentence": e.sentence,
                "facts": e.facts, "spend_pass_id": e.mandate_id, "disclosed": sorted(e.disclosed),
                "rule_ids": e.rule_ids, "order_id": e.order_id, "prev_hash": e.prev_hash, "hash": e.hash}
               for e in ctx.audit.list()]
    return LedgerView(entries=entries, chain={"ok": ok, "count": count, "broken_at": broken_at})


@router.get("/demo", response_model=DemoState)
def demo_state(ctx: CtxDep):
    return DemoState(stock_out_466375=ctx.stockout())


@router.post("/demo/stock-out", response_model=DemoState)
def stock_out(ctx: CtxDep, x_demo_token: Annotated[str | None, Header()] = None):
    """Simulated: Valio's test API cannot run out, so this sets 466375 to zero in stock."""
    _demo(ctx, x_demo_token)
    if not ctx.stockout():
        ctx.set_stockout(True)
    return DemoState(stock_out_466375=True)


@router.post("/demo/reset", response_model=DemoState)
def reset(ctx: CtxDep, x_demo_token: Annotated[str | None, Header()] = None):
    """Back to the state `make demo` starts from: drops every table, seeds again."""
    _demo(ctx, x_demo_token)
    ctx.reset()
    return DemoState(stock_out_466375=ctx.stockout())
