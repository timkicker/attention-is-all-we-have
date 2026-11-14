"""The web app's API under /api.

Reads and writes: a caller on this machine needs nothing more; anyone else needs the kitchen token
(VALIDIO_KITCHEN_TOKEN) as the X-Kitchen-Token header or the cookie POST /api/session sets, and finds the
API closed while no token is configured. VALIDIO_PUBLIC_READ=1 opens the GET routes to anyone, for the
public demo; every write still needs the token.
Approve and reject: the 6 digit code (VALIDIO_APPROVE_CODE) as X-Approve-Code or {"code"}. The order is
looked up first, so an unknown id answers 404 whatever the code. Five wrong codes lock that order, and five
from one client lock that client.
Demo reset: a logged-in demo copy (docs/ACCOUNTS-API.md), or the local kitchen with VALIDIO_DEMO=1 for a
caller on this machine. Nothing here orders: only an agent over MCP or the agent API does. Without a code, approve stays closed to anyone not on this machine."""

import hmac
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Request, Response

from ..audit.log import head_signature_ok
from ..demo.seed import SPEND_PASS_ID
from ..matching.need import CLAIM_NAMES
from ..policy.mandate import DEMO_SD_FIELDS
from . import display
from .accounts import request_ctx
from .schemas import (
    ApproveIn,
    AskedFor,
    DemoState,
    InboxItem,
    LedgerHeadView,
    LedgerView,
    OrderView,
    ResetIn,
    SessionIn,
    SpendPassIn,
    SpendPassView,
    SupplyRequestView,
)
from .state import MAX_CODE_TRIES, Ctx
from .tools import get_order, get_request

CtxDep = Annotated[Ctx, Depends(request_ctx)]
HELSINKI = timezone(timedelta(hours=2))
COOKIE = "validio_kitchen"


def _same(given: str | None, secret: str) -> bool:
    return hmac.compare_digest((given or "").encode(), secret.encode())


def _host(request: Request) -> str | None:
    return request.client.host if request.client else None


def kitchen(request: Request, ctx: CtxDep) -> None:
    """The gate in front of every /api route but health, session and the account routes."""
    if ctx.account is not None:
        return  # a logged-in kitchen works on its own store
    if ctx.is_local(_host(request)):
        return
    if ctx.public_read and request.method in ("GET", "HEAD"):
        return  # VALIDIO_PUBLIC_READ=1: anyone may look; writes still need the token, approve the code
    if not ctx.kitchen_token:
        raise HTTPException(403, "this server has no VALIDIO_KITCHEN_TOKEN, so the web API is closed to "
                                 "callers that are not on this machine")
    given = request.headers.get("x-kitchen-token") or request.cookies.get(COOKIE)
    if not _same(given, ctx.kitchen_token):
        raise HTTPException(401, "wrong or missing kitchen token")


router = APIRouter(prefix="/api", tags=["web"], dependencies=[Depends(kitchen)])
session_router = APIRouter(prefix="/api", tags=["web"])


@session_router.post("/session", status_code=204)
def session(ctx: CtxDep, request: Request, body: SessionIn) -> Response:
    """Trade the kitchen token for a cookie, so the web app need not send the header itself."""
    if not ctx.kitchen_token or not _same(body.token, ctx.kitchen_token):
        raise HTTPException(401, "wrong kitchen token")
    r = Response(status_code=204)
    r.set_cookie(COOKIE, ctx.kitchen_token, httponly=True, samesite="strict",
                 secure=request.url.scheme == "https", max_age=12 * 3600)
    return r


def check_code(ctx: Ctx, request: Request, key: str, header: str | None, body: ApproveIn | None) -> None:
    """The approval code, for an order or a Steady Order button (`key`). Five wrong codes lock that key,
    five from one client lock the client. Which code counts is `ctx.code_ok`: the account's own, 246810 on a
    demo copy, VALIDIO_APPROVE_CODE for the local kitchen."""
    if not ctx.has_code:
        if ctx.is_local(_host(request)):
            return
        raise HTTPException(403, "this server has no VALIDIO_APPROVE_CODE, so approval is closed")
    keys = [("key", key), ("client", _host(request) or "?")]
    if any(ctx.code_tries.get(k, 0) >= MAX_CODE_TRIES for k in keys):
        raise HTTPException(429, "too many wrong codes, approval is locked")
    given = header or (body.code if body else None)
    if not ctx.code_ok(given):
        for k in keys:
            ctx.code_tries[k] = ctx.code_tries.get(k, 0) + 1
        raise HTTPException(403, "wrong or missing approval code")


def _code(ctx: Ctx, request: Request, order_id: str, header: str | None, body: ApproveIn | None) -> None:
    ctx.orders.get(order_id)  # 404 for an id that does not exist, before the code is looked at
    check_code(ctx, request, order_id, header, body)


def _demo(ctx: Ctx, request: Request) -> None:
    """The demo reset: a demo copy's session, or the local kitchen (VALIDIO_DEMO=1) from this machine."""
    if ctx.account is not None:
        if not ctx.account["is_demo"]:
            raise HTTPException(404, "demo controls are only on the demo kitchen")
        return
    if not ctx.settings.demo:
        raise HTTPException(404, "demo controls are off")
    if not ctx.is_local(_host(request)):
        raise HTTPException(403, "demo controls are only on the demo kitchen")


@router.get("/inbox", response_model=list[InboxItem], response_model_exclude_none=True)
def inbox(ctx: CtxDep):
    out = []
    for r in reversed(ctx.store.requests()):
        v = get_request(ctx, r["id"])
        sentence = v.question if v.status == "waiting" and v.question else (v.decision.sentence if v.decision else "")
        why = None
        if v.status == "waiting" and v.decision:
            asked = asked_apart(ctx, v).asked_for
            why = ("Out of stock (simulated). The swap needs you." if asked and asked.state_text.startswith("Simulated stock-out")
                   else display.asks_text(v.decision.sentence))
        out.append(InboxItem(id=v.id, created_at=v.created_at, text=v.text, status=v.status, sentence=sentence,
                             total_cents=v.total_cents, title=v.title, title_text=v.title_text, summary=why))
    return out


@router.get("/requests/{request_id}", response_model=SupplyRequestView, response_model_exclude_none=True)
def request_detail(ctx: CtxDep, request_id: str):
    v = asked_apart(ctx, get_request(ctx, request_id))
    if v.status == "waiting" and not v.lead_text and v.decision:
        v.lead_text = display.reason_text(v.decision.sentence)  # why it waits, under the question
    return v


def asked_apart(ctx: Ctx, v: SupplyRequestView) -> SupplyRequestView:
    """The product the request named, when Validio turned it down, leaves the option lists and stands as
    `askedFor`: the lane count, the tabs and "Why not the others" then count the same options."""
    from ..demo.seed import STOCKOUT_ID
    from ..text.format import qty_text
    from . import display

    for ln in v.lines:
        pid = ln.need.product_id
        if not pid:
            continue
        lists = [ln.options, ln.substitutes or [], ln.beyond_list or []]
        hit = next((o for xs in lists for o in xs if o.product_id == pid), None)
        if hit is None or hit.verdict not in display.TURNED_DOWN:
            continue
        for xs in lists:
            xs[:] = [o for o in xs if o.product_id != pid]
        state = hit.group_text or "Turned down"
        if pid == STOCKOUT_ID and ctx.stockout():
            real = ctx.real_stock()
            state = "Simulated stock-out for this demo." + (f" Valio's live count is {qty_text(*real)}." if real else "")
            name = hit.short_name or hit.name
            if real:
                v.live_count_text = f"Valio's live count of {name[:1].lower()}{name[1:]}: {qty_text(*real)}."
            chosen = next((o for xs in lists for o in xs if o.verdict == "chosen"), None)
            swap = ("No swap found." if chosen is None or not chosen.is_substitute
                    else "Swap from Valio's list." if chosen.on_valio_list else "Swap not on Valio's list.")
            v.lead_text = f"Out of stock (simulated). {swap}"
        v.asked_for = AskedFor(product_id=pid, display_name=hit.short_name or hit.name, state_text=state)
        break
    return v


def _show_issued(ctx: Ctx) -> dict:
    """Spend Pass M-1 as the kitchen signed it last, the fields the agent discloses: the current version, also
    right after a re-sign the agent has not shown yet (Rules, Diet, connect)."""
    from ..agent.holder import DISCLOSE
    from ..demo import seed
    from ..orders.service import mandate_dict
    from ..policy.mandate import _mandate

    # read from the kitchen's own copy, not presented: the pass may be bound to an agent's key we do not hold,
    # and looking at it is no agent call (no nonce, no pause check)
    claims = seed.issued_claims(seed.issuance(ctx.db_path))
    m = _mandate({k: v for k, v in claims.items() if k not in DEMO_SD_FIELDS or k in DISCLOSE})
    return json.loads(json.dumps(mandate_dict(m)))


@router.get("/spend-passes/{pass_id}", response_model=SpendPassView, response_model_exclude_none=True)
def spend_pass(ctx: CtxDep, pass_id: str):
    """M-1 as the kitchen signed it last; any other pass as the agent last showed it. Fields it does not
    disclose stay absent."""
    m = _show_issued(ctx) if pass_id == SPEND_PASS_ID else ctx.store.seen_pass(pass_id)
    if m is None:
        raise HTTPException(404, f"no agent has shown Spend Pass {pass_id} yet")
    shown = sorted(m["disclosed"])
    return SpendPassView(
        id=m["id"], issuer=m["issuer"], holder=m["holder"],
        valid_from=datetime.fromtimestamp(m["not_before"], HELSINKI).isoformat(),
        valid_to=datetime.fromtimestamp(m["expires"], HELSINKI).isoformat(),
        auto_limit_cents=m["auto_limit_cents"], hard_cap_cents=m["hard_cap_cents"],
        week_cap_cents=m.get("week_cap_cents"),
        diet=[CLAIM_NAMES.get(d, d) for d in m["diet"]] if m["diet"] is not None else None,
        categories=m["categories"], deliver_by=m["deliver_by"], substitutes=m["substitutes"],
        split={"max_extra_cost_pct": m["split_max_extra_bp"] / 100, "allow_listed_substitutes": m["split_allow_listed"]},
        disclosed=shown, hidden=sorted(DEMO_SD_FIELDS - set(shown)), used_cents=ctx.orders.used_cents(pass_id),
    )


@router.post("/spend-pass", response_model=SpendPassView, response_model_exclude_none=True)
def sign_spend_pass(ctx: CtxDep, request: Request, body: SpendPassIn,
                    x_approve_code: Annotated[str | None, Header()] = None):
    """The owner signs Spend Pass M-1 again with new limits. Same id and validity window, so what the week
    already placed still counts; the copy the agent held before is refused from now on. One ledger entry."""
    from ..policy.mandate import SUBSTITUTES_LISTED
    from ..text.format import money
    from .settings import resign

    check_code(ctx, request, "spend-pass", x_approve_code, body)
    if body.auto_limit_cents > body.hard_cap_cents:
        raise HTTPException(422, f"alone up to {money(body.auto_limit_cents)} is above never above "
                                 f"{money(body.hard_cap_cents)}")
    changes = {"autoLimitCents": body.auto_limit_cents, "hardCapCents": body.hard_cap_cents,
               "diet": sorted(set(body.diet)), "deliverBy": body.deliver_by.isoformat(),
               "substitutes": SUBSTITUTES_LISTED if body.substitutes else "never"}
    resign(ctx, changes, "Rules changed")
    return spend_pass(ctx, SPEND_PASS_ID)


@router.get("/orders/{order_id}", response_model=OrderView, response_model_exclude_none=True)
def order(ctx: CtxDep, order_id: str):
    return get_order(ctx, order_id)


@router.post("/orders/{order_id}/approve", response_model=OrderView, response_model_exclude_none=True)
def approve(ctx: CtxDep, request: Request, order_id: str, body: Annotated[ApproveIn | None, Body()] = None,
            x_approve_code: Annotated[str | None, Header()] = None):
    """Approve a waiting order. Validio asks Valio again and refuses if a price rose more than 2 %, a
    line can no longer be delivered, the cut-off or the deadline has passed or the Spend Pass is no
    longer valid. A placed order cannot be approved twice."""
    _code(ctx, request, order_id, x_approve_code, body)
    return OrderView.model_validate(ctx.orders.approve(order_id, approver="owner"))


@router.post("/orders/{order_id}/reject", response_model=OrderView, response_model_exclude_none=True)
def reject(ctx: CtxDep, request: Request, order_id: str, body: Annotated[ApproveIn | None, Body()] = None,
           x_approve_code: Annotated[str | None, Header()] = None):
    _code(ctx, request, order_id, x_approve_code, body)
    return OrderView.model_validate(ctx.orders.reject(order_id, approver="owner"))


@router.get("/ledger", response_model=LedgerView, response_model_exclude_none=True)
def ledger(ctx: CtxDep):
    ok, count, broken_at = ctx.audit.verify()
    entries = [{"seq": e.seq, "at": e.at, "actor": e.actor, "kind": e.kind, "sentence": e.sentence,
                "facts": e.facts, "spend_pass_id": e.mandate_id, "disclosed": sorted(e.disclosed),
                "rule_ids": e.rule_ids, "order_id": e.order_id, "prev_hash": e.prev_hash, "hash": e.hash}
               for e in ctx.audit.list()]
    from . import display
    from .connect import agent_names
    from .steady import _steady

    names = agent_names(ctx)  # an agent's entries under the name it connected with ("Claude Code")
    titles: dict[str, tuple[str, str]] = {}  # request id: (title with the date, without)
    for e, rid in zip(entries, _request_ids(ctx, entries), strict=True):
        e["request_id"] = rid
        if e["actor"] in names:
            e["actor_text"] = names[e["actor"]]
        if rid and rid not in titles:
            if rid.startswith("M-"):
                titles[rid] = ("Rules", "Rules")
            elif rid == "demo":
                titles[rid] = ("Demo", "Demo")
            elif rid.startswith("R-"):
                v = get_request(ctx, rid)
                titles[rid] = (v.title, v.title_text or v.title)
            else:
                so = _steady()[0]
                titles[rid] = (so.name, so.name) if so.id == rid else (rid, rid)
        e["display_text"] = display.ledger_text(e["kind"], display.actor(e["actor"]), e["sentence"],
                                                titles[rid][0] if rid and e["kind"] == "request" else None,
                                                order_id=e.get("order_id"))
    groups = [{"request_id": rid, "title_text": t[1]} for rid, t in titles.items()]
    return LedgerView(entries=entries, chain={"ok": ok, "count": count, "broken_at": broken_at}, groups=groups)


def _request_ids(ctx: Ctx, entries: list[dict]) -> list[str | None]:
    """Which request or Steady Order each entry belongs to, so the ledger can group by it. An entry with an
    order takes that order's; a request entry starts the next request; a limits change is its pass's; a
    simulation is the demo's own ("demo"); anything else goes to the request before it."""
    owner = {o["id"]: o.get("requestId") for o in ctx.store.orders()}
    owner.update({oid: sid for oid, sid in ctx.store.steady_orders().items() if not owner.get(oid)})
    asked = iter(r["id"] for r in ctx.store.requests())
    out: list[str | None] = []
    current: str | None = None
    for e in entries:
        steady = re.match(r"Steady Order (S-\d+)", e["sentence"])
        if e.get("order_id") and owner.get(e["order_id"]):
            rid = owner[e["order_id"]]
        elif steady:
            rid = steady.group(1)
        elif e["kind"] == "request":
            current = rid = next(asked, None)
        elif e["kind"] in ("spend_pass", "agent"):
            rid = e["spend_pass_id"]  # the owner's change belongs to the pass, not the request before it
        elif e["kind"] == "simulation":
            rid = "demo"  # the presenter's switches are their own group, never a request's
        else:
            rid = current
        out.append(rid)
    return out


@router.get("/ledger/head", response_model=LedgerHeadView, response_model_exclude_none=True)
def ledger_head(ctx: CtxDep):
    """The signed head: entry count, last hash and the time of the last entry, signed with the kitchen's key."""
    audit = ctx.audit
    head = audit.head()
    if head is None:
        raise HTTPException(409, "the ledger has no head")
    pub = audit.public
    return LedgerHeadView(count=head.count, hash=head.hash, at=head.at, signature=head.signature,
                          public_key=pub.export_public(as_dict=True) if pub is not None else None,
                          signature_ok=pub is not None and head_signature_ok(head, pub))


def _demo_state(ctx: Ctx, on: bool) -> DemoState:
    real = ctx.real_stock()
    mode = getattr(ctx.valio, "mode", None)
    return DemoState(stock_out_466375=on, code_required=ctx.has_code, valio_down=ctx.valio_down(),
                     valio_mode=mode, valio_mode_text=display.valio_mode_text(mode),
                     real_stock_466375={"quantity": real[0], "unit": real[1]} if real else None)


@router.get("/demo", response_model=DemoState, response_model_exclude_none=True)
def demo_state(ctx: CtxDep):
    return _demo_state(ctx, ctx.stockout())


@router.post("/demo/reset", response_model=DemoState, response_model_exclude_none=True)
def reset(ctx: CtxDep, request: Request, body: Annotated[ResetIn | None, Body()] = None):
    """Back to the state `make demo` starts from: drops every table, seeds again. A demo copy goes back to the
    template, or with {"fresh": true} to the plain seed with no agent connected."""
    _demo(ctx, request)
    ctx.reset(fresh=bool(body and body.fresh))
    return _demo_state(ctx, ctx.stockout())
