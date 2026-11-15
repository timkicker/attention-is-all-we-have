"""Home and Activity for the web app (docs/ACCOUNTS-API.md, "Home and Activity").

GET /api/home             the agent, this week's spend, the setup steps, what waits for you, the newest five
GET /api/activity         every request and Steady Order as one item, newest first; ?status= filters, counts count
GET /api/activity/{id}    one item read top to bottom: what the agent asked, what Validio checked at Valio, the
                          rule that decided, the result or the approval, the ledger entries as proof

Everything here is composed from the views that already exist (requests, orders, Steady Orders, the ledger, the
Rules and the agent link); nothing decides, nothing is stored. A request the agent was cleared to order automatically
but has not confirmed yet ("working") is no item until it is ordered."""

import re
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import Field

from ..demo import seed
from ..matching.need import CLAIM_NAMES
from ..orders.explain import reason
from ..text.format import cap, display_name, money, unit_word
from . import connect, display, ui
from .schemas import Model, RankedOptionView, SupplyRequestView
from .settings import current_claims, rules_saved
from .state import Ctx
from .tools import get_order, get_request

Status = Literal["ordered", "waiting", "blocked", "standing"]
STATUSES: tuple[str, ...] = ("ordered", "waiting", "blocked", "standing")
# a request's status as Activity says it; "working" has no item
REQUEST_STATUS = {"ordered_alone": "ordered", "approved": "ordered", "ordered": "ordered", "waiting": "waiting",
                  "rejected": "blocked", "blocked": "blocked"}
CHECKED = ("attested", "attested_until", "consistent")
LATEST = 5


class ActivityItem(Model):
    id: str
    kind: Literal["request", "standing"]
    status: Status
    title: str
    why: str
    total_cents: int | None
    at: str
    order_id: str | None
    approved_by_you: bool = Field(False, description="ordered because the owner approved it, not automatically")


class Counts(Model):
    all: int
    ordered: int
    waiting: int
    blocked: int
    standing: int


class ActivityList(Model):
    items: list[ActivityItem]
    counts: Counts


class Asked(Model):
    text: str
    agent_name: str


class Check(Model):
    label: Literal["Product", "Price", "Stock", "Allergens", "Substitute"]
    value: str
    note: str | None
    ok: bool | None


class RuleUsed(Model):
    text: str
    version: int


class Result(Model):
    order_id: str
    delivery: str | None
    order_ids: list[str] = Field(default_factory=list, description="every order placed: one for a request, one per "
                                 "renewed line for the Steady Order")


class Approval(Model):
    order_id: str
    hold_until: str


class Proof(Model):
    at: str
    actor: str
    text: str
    hash: str


class ActivityDetail(Model):
    item: ActivityItem
    asked: Asked
    checks: list[Check]
    rule: RuleUsed
    result: Result | None
    approval: Approval | None
    proof: list[Proof]


class HomeAgent(Model):
    state: Literal["none", "pairing", "consent", "active", "paused"]
    name: str | None
    last_used_at: str | None


class Week(Model):
    used_cents: int
    cap_cents: int | None


class HomeSetup(Model):
    rules_saved: bool
    agent_connected: bool
    first_order: bool


class Home(Model):
    agent: HomeAgent
    week: Week
    setup: HomeSetup
    needs_you: list[ActivityItem]
    latest: list[ActivityItem]


# requests


def _decided(ctx: Ctx, rid: str) -> str:
    """The sentence Validio decided with when the request came in; the view swaps it for the order's latest."""
    raw = ctx.store.request(rid) or {}
    return (raw.get("decision") or {}).get("sentence") or ""


def _why(ctx: Ctx, v: SupplyRequestView) -> str:
    """One plain line in the Rules' words, with no full stop."""
    decided = _decided(ctx, v.id)
    if v.status == "ordered_alone":
        alone = re.search(r"inside the auto limit of ([\d,.]+ €)", decided)
        return f"Under your {alone.group(1)} limit, ordered automatically" if alone else "Ordered automatically"
    if v.status in ("approved", "ordered"):
        return "You approved it"
    if v.status == "rejected":
        return "You said no"
    if v.status == "waiting":
        return (display.reason_text(decided) or "Waiting for you").rstrip(".")
    return _blocked(v.decision.sentence if v.decision else decided)


def _blocked(sentence: str) -> str:
    over = re.search(r"over the (?:hard cap of ([\d,.]+ €)|([\d,.]+ €) never-above limit)", sentence)
    if over:
        return f"Above your {over.group(1) or over.group(2)} limit, blocked"
    if "diet rule" in sentence and "contradicted" in sentence:
        return "Breaks your diet and allergen rules, blocked"
    if re.search(r"outside the Spend Pass's product groups \(", sentence):  # names the groups: in the Rules' words
        why = reason({"sentence": sentence, "outcome": "blocked"})[1]
        return why[:1].upper() + why[1:]
    head = re.search(r"Blocked: ([^.]+)", sentence)
    if head:
        first = re.split(r", (?!\d)| and ", head.group(1), maxsplit=1)[0]
        return f"Blocked: {first}"
    return (display.summary(sentence) or "Blocked").rstrip(".")


def _rule_text(ctx: Ctx, v: SupplyRequestView, why: str) -> str:
    if v.status in ("approved", "ordered"):
        said = display.reason_text(_decided(ctx, v.id))
        return f"{said} You approved it." if said else "You approved it."
    return why + "."


def _request_item(ctx: Ctx, v: SupplyRequestView) -> ActivityItem | None:
    status = REQUEST_STATUS.get(v.status)
    if status is None:
        return None
    return ActivityItem(id=v.id, kind="request", status=status, title=v.title_text or v.title or v.id,
                        why=_why(ctx, v), total_cents=v.total_cents, at=v.created_at, order_id=v.order_id,
                        approved_by_you=v.status in ("approved", "ordered"))


def _fact(o: RankedOptionView, field: str):
    return next((f for f in o.facts if f.field == field), None)


def _ok(grade: str | None) -> bool | None:
    if grade in CHECKED:
        return True
    return False if grade == "contradicted" else None


def _checks(v: SupplyRequestView) -> list[Check]:
    """What Validio checked at Valio for each product it chose: the product, price, stock, allergens and, for a
    swap, whether Valio lists it."""
    out: list[Check] = []
    for o, diet in _chosen(v):
        out.append(Check(label="Product", value=o.full_name or o.name, note=o.qty_text, ok=True))
        price = _fact(o, "price")
        if price is not None:
            out.append(Check(label="Price", value=f"{price.value_text or price.value} per {_per(o)}",
                             note=f"Valio price, {price.note_text}" if price.note_text else "Valio price",
                             ok=_ok(price.grade)))
        stock = _fact(o, "quantity")
        if stock is not None:
            out.append(Check(label="Stock", value=str(stock.value_text or stock.value or "unknown"),
                             note=stock.note_text or None, ok=_ok(stock.grade)))
        claims = [f for f in o.facts if f.field.startswith("claim:")
                  and CLAIM_NAMES.get(f.field[6:]) in diet]
        allergens = _fact(o, "allergens")
        contains = None
        if allergens is not None and allergens.value == "none contained":
            contains = "Contains no listed allergen"
        elif allergens is not None and allergens.value:
            contains = f"Contains {allergens.value_text or allergens.value}"
        if claims:
            grades = [f.grade for f in claims]
            ok = False if "contradicted" in grades else True if all(g in CHECKED for g in grades) else None
            out.append(Check(label="Allergens", value=cap(display.and_list([str(f.value_text) for f in claims])),
                             note=contains, ok=ok))
        elif allergens is not None:
            out.append(Check(label="Allergens", value=contains or "No allergen data", note=None,
                             ok=None if allergens.grade == "missing" else True))
        if o.is_substitute:
            out.append(Check(label="Substitute", value="On Valio's list" if o.on_valio_list else "Not on Valio's list",
                             note=o.short_text, ok=bool(o.on_valio_list)))
    return [c.model_copy(update={"note": _note(c.value, c.note)}) for c in out]


def _note(value: str, note: str | None) -> str | None:
    """The note as one plain line under its value: no full stop, and not the value said again ("Valio gives no
    real count" over "Valio gives no real count, treated as in stock" reads "Treated as in stock")."""
    if not note:
        return None
    note = note.strip().rstrip(".")
    if note.lower().startswith(value.lower()):
        note = note[len(value):].lstrip(" ,;:")
    return cap(note) if note else None


def _per(o: RankedOptionView) -> str:
    """What one price buys: "1 l pack" for a product with a pack size, else the sales unit, "piece"."""
    one = display.qty(1, o.unit, o.product_id) or ""
    if "×" in one:
        return one.split("×", 1)[1].strip() + " pack"
    return unit_word(o.unit, 1) or "unit"


def _chosen(v: SupplyRequestView) -> list[tuple[RankedOptionView, list[str]]]:
    """The option Validio chose on each line, with the diet that line asked for."""
    out = []
    for ln in v.lines:
        pid = ln.chosen.product_id if ln.chosen else None
        o = next((o for xs in (ln.options, ln.substitutes or [], ln.beyond_list or []) for o in xs
                  if o.product_id == pid), None)
        if o is not None:
            out.append((o, ln.need.diet))
    return out


def version_at(ctx: Ctx, at: str, pass_id: str = seed.SPEND_PASS_ID) -> int:
    """The version of the pass that was in force at `at`: the newest one signed at or before it."""
    when = datetime.fromisoformat(at)
    versions = seed.pass_versions(ctx.db_path, pass_id)
    signed = [v["version"] for v in versions if v["at"] and datetime.fromisoformat(v["at"]) <= when]
    return max(signed, default=min((v["version"] for v in versions), default=1))


def _hold_until(ctx: Ctx, v: SupplyRequestView) -> str:
    """Until when an approval can still go through: the earliest order cut-off Valio gave for the chosen
    products, else the end of the pass. Approve asks Valio again either way."""
    cutoffs = [str(f.value) for o, _ in _chosen(v) for f in o.facts if f.field == "cutoff" and f.value]
    if cutoffs:
        return min(cutoffs, key=datetime.fromisoformat)
    claims = current_claims(ctx.db_path)
    return datetime.fromtimestamp(claims["exp"], ctx.now().tzinfo).isoformat()


def _proof(ctx: Ctx, item_id: str) -> list[Proof]:
    return [Proof(at=e.at, actor=e.actor_text or display.actor(e.actor), text=e.display_text or e.sentence,
                  hash=e.hash)
            for e in ui.ledger(ctx).entries if e.request_id == item_id]


def _request_detail(ctx: Ctx, rid: str) -> ActivityDetail:
    v = get_request(ctx, rid)
    item = _request_item(ctx, v)
    if item is None:
        raise HTTPException(404, f"{rid} is not decided yet")
    names = connect.agent_names(ctx)
    result = approval = None
    if v.order_id:
        o = get_order(ctx, v.order_id)
        if o.state == "placed":
            result = Result(order_id=o.id, delivery=min((ln.delivery_date for ln in o.lines if ln.delivery_date),
                                                        default=None), order_ids=[o.id])
        elif o.state == "waiting":
            approval = Approval(order_id=o.id, hold_until=_hold_until(ctx, v))
    return ActivityDetail(
        item=item, asked=Asked(text=v.agent_text or v.text, agent_name=names.get(v.agent) or display.actor(v.agent)),
        checks=_checks(v), rule=RuleUsed(text=_rule_text(ctx, v, item.why), version=version_at(ctx, v.created_at)),
        result=result, approval=approval, proof=_proof(ctx, rid))


# Steady Orders


def _standing(request: Request) -> list:
    from .steady import steady_list

    return steady_list(request)


def _standing_at(ctx: Ctx, so) -> str:
    """When the Steady Order last did something: its renewal, else its last ledger entry, else the start of its
    pass."""
    if so.renewed_at:
        return so.renewed_at
    mine = [e.at for e in ui.ledger(ctx).entries if e.request_id == so.id]
    if mine:
        return max(mine, key=datetime.fromisoformat)
    from .steady import _pass

    m = _pass(ctx.db_path, ctx.keys_dir)
    return datetime.fromtimestamp(m.not_before, ctx.now().tzinfo).isoformat()


LINE_OK = {"renewed": True, "split_renewed": True, "accepted": True, "waiting": None, "flagged": None,
           "blocked": False}
ORDERED_LINE = frozenset(k for k, v in LINE_OK.items() if v)


def _standing_item(ctx: Ctx, request: Request, so) -> ActivityItem:
    """One line for the Steady Order: its lines, how many wait for the owner and how many were blocked this
    week, and what the ordered lines cost (none before it was renewed)."""
    from .steady import steady_order

    full = steady_order(request, so.id)
    lines = f"{so.line_count} line{'s' if so.line_count != 1 else ''}"
    waiting = sum(1 for ln in full.lines if LINE_OK.get(ln.result, None) is None)
    blocked = sum(1 for ln in full.lines if ln.result == "blocked")
    flags = (f", {waiting} waiting for you" if waiting and full.renewed_at else "") + \
        (f", {blocked} blocked" if blocked else "")
    ordered = [ln.total_cents for ln in full.lines if ln.result in ORDERED_LINE and ln.total_cents is not None]
    return ActivityItem(id=so.id, kind="standing", status="standing", title=so.name,
                        why=f"Every {so.weekday}, {lines}{flags}", total_cents=sum(ordered) if ordered else None,
                        at=_standing_at(ctx, so), order_id=None)


def _standing_detail(ctx: Ctx, request: Request, sid: str) -> ActivityDetail:
    from .steady import steady_order

    so = next((s for s in _standing(request) if s.id == sid), None)
    if so is None:
        raise HTTPException(404, f"no Steady Order {sid}")
    full = steady_order(request, sid)
    item = _standing_item(ctx, request, so)
    ids = list(dict.fromkeys(ln.order_id for ln in full.lines if ln.result in ORDERED_LINE and ln.order_id))
    days = [ln.delivery_date for oid in ids for ln in get_order(ctx, oid).lines if ln.delivery_date]
    result = Result(order_id=ids[0], order_ids=ids, delivery=min(days, default=None)) if ids else None
    checks = [Check(label="Product", value=(v := display_name(ln.name)), note=_note(v, _line_note(ln)),
                    ok=LINE_OK.get(ln.result)) for ln in full.lines]
    sp = full.steady_pass
    limits = (f"Under the Steady Order's own pass: orders automatically up to {money(sp.auto_limit_cents)}, blocked above "
              f"{money(sp.hard_cap_cents)}." if sp and sp.auto_limit_cents is not None and sp.hard_cap_cents is not None
              else "Under the Steady Order's own pass.")
    weeks = f", learned from {full.weeks_learned} weeks" if full.weeks_learned else ""
    return ActivityDetail(
        item=item, asked=Asked(text=f"{full.name}: the usual lines every {full.weekday}{weeks}.", agent_name="Validio"),
        checks=checks, rule=RuleUsed(text=limits, version=seed.pass_version(ctx.db_path, seed.STEADY_PASS_ID)),
        result=result, approval=None, proof=_proof(ctx, sid))


def _line_note(ln) -> str | None:
    texts = ln._texts()
    qty = texts.get("qty_text") or texts.get("usual_qty_text")
    return texts.get("short_text") or qty


# all of it


def items(ctx: Ctx, request: Request) -> list[ActivityItem]:
    """Every item, newest first."""
    out = [it for r in ctx.store.requests() if (it := _request_item(ctx, get_request(ctx, r["id"]))) is not None]
    out += [_standing_item(ctx, request, so) for so in _standing(request)]

    def key(it: ActivityItem):
        n = re.search(r"\d+$", it.id)
        return datetime.fromisoformat(it.at), it.kind == "request", int(n.group()) if n else 0

    return sorted(out, key=key, reverse=True)


def _agent(ctx: Ctx) -> HomeAgent:
    s = connect.view(ctx)
    name = s.agent.name if s.agent else s.consent.name if s.consent else None
    return HomeAgent(state=s.state, name=name, last_used_at=s.agent.last_used_at if s.agent else None)


router = APIRouter(prefix="/api", tags=["web"], dependencies=[Depends(ui.kitchen)])


@router.get("/home", response_model=Home)
def home(ctx: ui.CtxDep, request: Request):
    """Home in one call. `week.usedCents` is what placed orders under the Rules' pass add up to, `capCents` the
    Rules' per week limit (null without one)."""
    all_items = items(ctx, request)
    claims = current_claims(ctx.db_path)
    agent = _agent(ctx)
    return Home(
        agent=agent,
        week=Week(used_cents=ctx.orders.used_cents(seed.SPEND_PASS_ID), cap_cents=claims.get("weekCapCents")),
        setup=HomeSetup(rules_saved=rules_saved(ctx.db_path), agent_connected=agent.state in ("active", "paused"),
                        first_order=any(it.kind == "request" and it.status == "ordered" for it in all_items)),
        needs_you=[it for it in all_items if it.status == "waiting"],
        latest=all_items[:LATEST])


@router.get("/activity", response_model=ActivityList)
def activity(ctx: ui.CtxDep, request: Request,
             status: Annotated[Literal["all", "ordered", "waiting", "blocked", "standing"], Query()] = "all"):
    """Every request and Steady Order, newest first. `counts` count all items, whatever the filter."""
    all_items = items(ctx, request)
    counts = Counts(all=len(all_items), **{s: sum(it.status == s for it in all_items) for s in STATUSES})
    return ActivityList(items=[it for it in all_items if status == "all" or it.status == status], counts=counts)


@router.get("/activity/{item_id}", response_model=ActivityDetail)
def activity_detail(ctx: ui.CtxDep, request: Request, item_id: str):
    """A request (R-…) or a Steady Order (S-…). Approve and reject stay POST /api/orders/{orderId}/approve and
    /reject with `approval.orderId`."""
    if re.fullmatch(r"R-\d+", item_id):
        return _request_detail(ctx, item_id)
    if re.fullmatch(r"S-\d+", item_id):
        return _standing_detail(ctx, request, item_id)
    raise HTTPException(404, f"no activity {item_id}")
