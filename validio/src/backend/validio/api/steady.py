"""Steady Order routes for the web app, the shapes of src/frontend/src/lib/api/types.ts.

GET  /api/steady                              one summary per Steady Order
GET  /api/steady/{id}                         the order, its lines and, after a renewal, the results and flags
POST /api/steady/{id}/renew                   Drift Watch, then renewal. Renewed lines become orders at once,
                                              a second press orders nothing twice
POST /api/steady/{id}/lines/{pid}/accept      a person lets a waiting or flagged line through, it becomes an order

Both POST routes place orders, so they need the approve code like /api/orders/{id}/approve
(X-Approve-Code header or {"code": ...}).

Every decision goes to the ledger. The renewal state lives in validio.db next to the seed, so `make seed`
resets it too; the stores notice the new seed token and reopen.
"""

import json
import re
import sqlite3
import threading
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Body, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, model_serializer
from pydantic.alias_generators import to_camel

from ..audit.log import AuditLog
from ..catalog.store import Catalog
from ..config import load_settings
from ..demo import seed
from ..demo.clock import demo_now
from ..orders.service import ApproveRefused, LineIn, OrderError, OrderService
from ..orders.store import Store
from ..policy.mandate import Mandate
from ..standing.drift import unit_word
from ..standing.learn import learn
from ..standing.model import LineResult, RenewedLine, StandingOrder
from ..standing.renew import run
from ..text.format import cap, display_name, money, product_qty, qty_of, short_name
from ..text.format import unit_word as fmt_unit_word
from ..valio.client import ValioClient
from .schemas import ApproveIn

router = APIRouter(prefix="/api/steady", tags=["steady"])
ACTOR = "validio:steady-order"
CHEF = "owner"  # the person who accepts a Steady Order line approves like on any order (O5)
WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
STATE_SCHEMA = "create table if not exists steady_state (order_id text primary key, body text not null)"


class Camel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    def _texts(self) -> dict:
        """Text fields made from the raw ones when the view is sent, so a copied view never shows old text."""
        return {}

    @model_serializer(mode="wrap")
    def _with_texts(self, handler, info):
        out = handler(self)
        for k, v in self._texts().items():
            key = to_camel(k) if info.by_alias else k
            if v is None and info.exclude_none:
                out.pop(key, None)
            else:
                out[key] = v
        return out


class DriftFlagOut(Camel):
    kind: str
    sentence: str
    pct: int | None = None


class SplitPartOut(Camel):
    product_id: str
    name: str
    quantity: int
    unit: str
    total_cents: int
    on_valio_list: bool

    display_name: str | None = None
    short_name: str | None = None
    full_name: str | None = None
    qty_text: str | None = None
    money_text: str | None = None

    def _texts(self) -> dict:
        return {"display_name": short_name(self.name), "short_name": short_name(self.name),
                "full_name": display_name(self.name), "qty_text": _qty(self.quantity, self.product_id),
                "money_text": money(self.total_cents)}


class SplitOut(Camel):
    parts: list[SplitPartOut]
    total_cents: int
    extra_cost_cents: int
    extra_cost_pct: float


def _line_short(sentence: str, flags) -> str | None:
    """One short line for a held steady line: "None in stock at Valio.", "27 of 30 in stock."."""
    stop = re.match(r"Not renewed: ([^.]+)\.", sentence)
    if stop:
        return cap(stop.group(1)) + "."
    for f in flags:
        few = re.match(r"Only ([\d,]+) .*?in stock, the usual line is ([\d,]+)", f.sentence or "")
        if few:
            return f"{few.group(1)} of {few.group(2)} in stock."
    return None


class SteadyLineOut(Camel):
    product_id: str
    name: str
    unit: str
    usual_quantity: int
    this_week_quantity: int | None = None
    total_cents: int | None = None
    result: str
    sentence: str
    flags: list[DriftFlagOut] = []
    split: SplitOut | None = None
    accept_label: str | None = None
    history: list[int] | None = None
    order_id: str | None = None
    rule_ids: list[str] | None = None

    display_name: str | None = None
    short_name: str | None = None
    full_name: str | None = None
    usual_qty_text: str | None = None
    qty_text: str | None = None
    money_text: str | None = None
    short_text: str | None = None

    def _texts(self) -> dict:
        return {"short_text": _line_short(self.sentence, self.flags),
                "display_name": short_name(self.name), "short_name": short_name(self.name),
                "full_name": display_name(self.name), "usual_qty_text": _qty(self.usual_quantity, self.product_id),
                "qty_text": None if self.this_week_quantity is None else _qty(self.this_week_quantity, self.product_id),
                "money_text": None if self.total_cents is None else money(self.total_cents)}


def _state(renewed_at: str | None) -> tuple[str, str]:
    """One state for the whole order, so no line has to repeat it."""
    if not renewed_at:
        return "not_renewed", "Not renewed this week"
    from datetime import datetime
    t = datetime.fromisoformat(renewed_at)
    return "renewed", f"Renewed {t:%a} {t.day} {t:%b}, {t:%H:%M}"


class SteadyPassOut(Camel):
    """The Steady Orders' own weekly Spend Pass and what its placed orders already used (review 3 M1)."""
    id: str
    valid_from: str
    valid_to: str
    auto_limit_cents: int | None = None
    hard_cap_cents: int | None = None
    used_cents: int


class SteadyOrderOut(Camel):
    id: str
    name: str
    weekday: str
    guests_per_week: int
    weeks_learned: int
    simulated_history: bool
    renewed_at: str | None = None
    lines: list[SteadyLineOut]
    steady_pass: SteadyPassOut | None = None  # filled on every answer, never stored with the view

    state: str | None = None
    state_text: str | None = None

    def _texts(self) -> dict:
        state, text = _state(self.renewed_at)
        return {"state": state, "state_text": text}


class SteadyOrderSummaryOut(Camel):
    id: str
    name: str
    weekday: str
    line_count: int
    flag_count: int
    renewed_at: str | None = None

    state: str | None = None
    state_text: str | None = None

    def _texts(self) -> dict:
        state, text = _state(self.renewed_at)
        return {"state": state, "state_text": text}


@dataclass
class _Live:
    token: str
    path: Path
    store: Store
    audit: AuditLog
    service: OrderService
    keys: Path | None = None


class Runtime:
    """Catalog and Valio once, the stores per seed. A new seed token (after `make seed`) reopens them.

    Without a path the store is the local kitchen's (VALIDIO_DB, VALIDIO_KEYS). An account's runtime has its
    own path and keys and borrows the catalog and the Valio client of `shared`."""

    def __init__(self, path: Path | None = None, keys: Path | None = None, shared: "Runtime | None" = None):
        self.lock = threading.RLock()
        self._path, self._keys, self._shared = path, keys, shared
        self._live: _Live | None = None
        self._catalog: Catalog | None = None
        self._valio: ValioClient | None = None

    def db_path(self) -> Path:
        return self._path or seed.db_path()

    def keys_dir(self) -> Path:
        return self._keys or seed.keys_path()

    @property
    def settings(self):
        return load_settings()

    @property
    def catalog(self) -> Catalog:
        if self._shared is not None:
            return self._shared.catalog
        if self._catalog is None:
            self._catalog = Catalog(self.settings.catalog_db)
        return self._catalog

    @property
    def valio(self) -> ValioClient:
        if self._shared is not None:
            return self._shared.valio
        if self._valio is None:
            s = self.settings
            self._valio = ValioClient(s.valio_base_url, s.valio_api_key, s.valio_mode, s.valio_cache,
                                      customer=s.valio_customer)
        return self._valio

    def live(self) -> _Live:
        path = self.db_path()
        token = seed.seed_token(path)
        if token is None:
            seed.reset(path, self.keys_dir())
            token = seed.seed_token(path)
        if self._live is None or (self._live.token, self._live.path) != (token, path):
            if self._live is not None:
                self._live.service.closed = True  # a call that waited through a reset gets 503, not a dead store
                self._live.store.close()  # the ledger shares this connection, so it closes too
            store = Store(path)
            # an order and its ledger entry commit together; the kitchen key signs the head
            audit = AuditLog(path, seed.kitchen_key(self.keys_dir()), con=store.con, lock=store.lock)
            service = OrderService(store, self.catalog, self.valio, audit, clock=lambda: demo_now(self.settings.now, store.con),
                                   adjust=lambda avail: seed.apply_stockout(avail, seed.stockout(path)),
                                   lock=self.lock)  # one lock for every write and the demo reset
            self._live = _Live(token, path, store, audit, service, self.keys_dir())
        return self._live

    def close(self) -> None:
        with self.lock:
            if self._live is not None:
                self._live.service.closed = True
                self._live.store.close()
                self._live = None


runtime = Runtime()


def _con(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.execute(STATE_SCHEMA)
    return con


def _load(path: Path, order_id: str) -> dict | None:
    con = _con(path)
    try:
        row = con.execute("select body from steady_state where order_id = ?", (order_id,)).fetchone()
    finally:
        con.close()
    return json.loads(row[0]) if row else None


def _save(path: Path, order_id: str, body: dict) -> None:
    con = _con(path)
    try:
        con.execute("insert or replace into steady_state values (?, ?)", (order_id, json.dumps(body)))
        con.commit()
    finally:
        con.close()


def _ctx(request: Request):
    # the request's account, imported late: api.state imports this module
    from .accounts import request_ctx

    return request_ctx(request)


def _chef(ctx, request: Request, key: str, header: str | None, body) -> None:
    from .ui import check_code

    check_code(ctx, request, key, header, body)


def _refuse(path: Path, so_id: str, state: dict, view: SteadyOrderOut, idx: int, sentence: str,
            order_id: str) -> None:
    """The accept could not place the line. Keep the reason on the line, so a retry decides nothing new."""
    lines = list(view.lines)
    lines[idx] = lines[idx].model_copy(update={"result": str(LineResult.BLOCKED), "sentence": sentence,
                                               "accept_label": None, "order_id": order_id})
    _save(path, so_id, {**state, "view": _dump(view.model_copy(update={"lines": lines}))})
    raise HTTPException(409, sentence)


def _steady() -> tuple[StandingOrder, object]:
    h = seed.load_history()
    return learn(h), h


def _get_order(order_id: str) -> tuple[StandingOrder, object]:
    so, h = _steady()
    if order_id != so.id:
        raise HTTPException(404, f"No Steady Order with id {order_id}.")
    return so, h


def _pending(so: StandingOrder, h) -> SteadyOrderOut:
    cat = runtime.catalog
    out = []
    for ln in so.lines:
        amounts = [w.qty(ln.product_id) for w in h.weeks]
        varies = len(set(amounts)) > 1
        p = cat.get(ln.product_id)
        out.append(SteadyLineOut(
            product_id=ln.product_id, name=p.name_en if p else ln.product_id, unit=_unit(ln.product_id),
            usual_quantity=ln.sales_qty, result="pending",
            sentence=f"Median of the last {len(amounts)} weeks." if varies else "",
            history=amounts if varies else None))
    return SteadyOrderOut(id=so.id, name=so.name, weekday=WEEKDAY_NAMES[so.weekday], guests_per_week=so.guests,
                          weeks_learned=so.learned_from, simulated_history=so.simulated, lines=out)


_UNITS: dict[str, str] = {}


def _unit(pid: str) -> str:
    # the sales unit from the catalog in the words a chef reads
    if pid not in _UNITS:
        p = runtime.catalog.get(pid)
        su = p.sales_unit if p else ""
        _UNITS[pid] = fmt_unit_word(su) or "units"
    return _UNITS[pid]


def _qty_of(n: int, pid: str) -> str:
    return qty_of(n, runtime.catalog.get(pid))


def _qty(n: int, pid: str) -> str:
    p = runtime.catalog.get(pid)
    return product_qty(n, p)


def _line_out(pending: SteadyLineOut, rl: RenewedLine) -> SteadyLineOut:
    split = None
    # a split that renewed, or one that waits for the chef ("Order the split"): show what accept would order
    if rl.split is not None and (rl.result is LineResult.SPLIT_RENEWED
                                 or any(x.product.id != rl.product_id for x in rl.split.parts)):
        plan = rl.split
        split = SplitOut(
            parts=[SplitPartOut(product_id=x.product.id, name=x.product.name_en, quantity=x.sales_qty,
                                unit=unit_word(x.availability, x.product.sales_unit), total_cents=x.total_cents,
                                on_valio_list=x.on_valio_list) for x in plan.parts],
            total_cents=plan.total_cents, extra_cost_cents=plan.total_cents - plan.base_cents,
            extra_cost_pct=float(plan.extra_pct))
    return pending.model_copy(update={
        "this_week_quantity": rl.this_week_qty, "total_cents": rl.total_cents, "result": str(rl.result),
        "sentence": rl.sentence, "flags": [DriftFlagOut(kind=str(f.kind), sentence=f.sentence, pct=f.pct)
                                           for f in rl.flags],
        "split": split, "accept_label": rl.accept_label,
        "rule_ids": list(rl.decision.rule_ids) if rl.decision is not None else None,
    })


def _order_lines(rl: RenewedLine) -> tuple[list[LineIn], int | None]:
    if rl.result is LineResult.SPLIT_RENEWED:
        return ([LineIn(x.product.id, x.sales_qty, is_substitute=x.on_valio_list, on_valio_list=x.on_valio_list)
                 for x in rl.split.parts], rl.split.base_cents)
    return [LineIn(rl.product_id, rl.this_week_qty)], None


def _accept_lines(line: SteadyLineOut) -> tuple[list[LineIn], int | None]:
    """What accept orders: the split shown on the line, or this week's quantity of the product."""
    if line.split is not None:
        return ([LineIn(x.product_id, x.quantity, is_substitute=x.product_id != line.product_id,
                        on_valio_list=x.on_valio_list) for x in line.split.parts],
                line.split.total_cents - line.split.extra_cost_cents)
    return [LineIn(line.product_id, line.this_week_quantity)], None


def _pass(path, keys=None) -> Mandate:
    return seed.spend_pass(path, keys, now=runtime.settings.now, pass_id=seed.STEADY_PASS_ID)


def _with_pass(view: SteadyOrderOut, live) -> SteadyOrderOut:
    m = _pass(live.path, live.keys)
    tz = runtime.settings.now.tzinfo
    return view.model_copy(update={"steady_pass": SteadyPassOut(
        id=m.id, valid_from=datetime.fromtimestamp(m.not_before, tz).isoformat(),
        valid_to=datetime.fromtimestamp(m.expires, tz).isoformat(), auto_limit_cents=m.auto_limit_cents,
        hard_cap_cents=m.hard_cap_cents, used_cents=live.service.used_cents(m.id))})


def _view(state: dict) -> SteadyOrderOut:
    return SteadyOrderOut.model_validate(state["view"])


def _dump(view: SteadyOrderOut) -> dict:
    return view.model_dump(by_alias=False, exclude={"steady_pass"})


@router.get("", response_model=list[SteadyOrderSummaryOut], response_model_exclude_none=True)
def steady_list(request: Request):
    rt = _ctx(request).rt
    with rt.lock:
        live = rt.live()
        so, h = _steady()
        state = _load(live.path, so.id)
        view = _view(state) if state else _pending(so, h)
    flagged = [ln for ln in view.lines if ln.flags and ln.result != "accepted"]
    return [SteadyOrderSummaryOut(id=view.id, name=view.name, weekday=view.weekday, line_count=len(view.lines),
                                  flag_count=len(flagged), renewed_at=view.renewed_at)]


@router.get("/{order_id}", response_model=SteadyOrderOut, response_model_exclude_none=True)
def steady_order(request: Request, order_id: str):
    rt = _ctx(request).rt
    with rt.lock:
        live = rt.live()
        so, h = _get_order(order_id)
        state = _load(live.path, so.id)
        return _with_pass(_view(state) if state else _pending(so, h), live)


@router.post("/{order_id}/renew", response_model=SteadyOrderOut, response_model_exclude_none=True)
def steady_renew(request: Request, order_id: str, body: Annotated[ApproveIn | None, Body()] = None,
                 x_approve_code: Annotated[str | None, Header()] = None):
    ctx = _ctx(request)
    _chef(ctx, request, f"steady:{order_id}", x_approve_code, body)
    return renew(order_id, ctx.rt)


def renew(order_id: str, rt: Runtime | None = None) -> SteadyOrderOut:
    """The renewal behind the button, without the code check: the route checks the code, the agent's
    tool renew_steady_order checks the Spend Pass instead. Without `rt` it works on `get_ctx()`'s store."""
    if rt is None:
        from .state import get_ctx

        rt = get_ctx().rt
    with rt.lock:
        live = rt.live()
        so, h = _get_order(order_id)
        state = _load(live.path, so.id)
        if state:  # already renewed this week: nothing is ordered twice
            return _with_pass(_view(state), live)
        now = live.service.clock()
        mandate = _pass(live.path, live.keys)
        renewal = run(so, h, rt.catalog, rt.valio, mandate, now, stockout=seed.stockout(live.path))
        pending = {ln.product_id: ln for ln in _pending(so, h).lines}
        diet = {ln.product_id: ln.diet for ln in so.lines}
        out = []
        for rl in renewal.lines:
            line = _line_out(pending[rl.product_id], rl)
            if rl.result in (LineResult.RENEWED, LineResult.SPLIT_RENEWED):
                order_lines, base = _order_lines(rl)
                o = live.service.submit(
                    mandate=mandate, lines=order_lines, deliver_by=renewal.delivery,
                    idempotency_key=f"steady:{so.id}:{renewal.delivery}:{rl.product_id}", actor=ACTOR,
                    required_claims=diet[rl.product_id], split_base_cents=base)
                line = line.model_copy(update={"order_id": o["id"]})
                if o["state"] != "placed":  # Valio's second answer changed the picture: a person looks
                    line = line.model_copy(update={"result": "waiting", "sentence": o["decision"]["sentence"],
                                                   "accept_label": "Order anyway"})
            else:
                flags = " ".join(f.sentence for f in rl.flags if f.sentence not in rl.sentence)
                live.audit.append(
                    at=live.service.clock(), actor="validio", kind="decision",
                    sentence=f"Steady Order {so.id}, {_qty_of(rl.usual_qty, rl.product_id)}: {rl.sentence}" + (f" {flags}" if flags else ""),
                    facts=[], mandate_id=mandate.id, disclosed=mandate.disclosed,
                    rule_ids=list(rl.decision.rule_ids) if rl.decision is not None else [], order_id=None)
            out.append(line)
        view = _pending(so, h).model_copy(update={"lines": out, "renewed_at": now.isoformat()})
        _save(live.path, so.id, {"view": _dump(view), "delivery": renewal.delivery.isoformat()})
        return _with_pass(view, live)


@router.post("/{order_id}/lines/{product_id}/accept", response_model=SteadyOrderOut,
             response_model_exclude_none=True)
def steady_accept(request: Request, order_id: str, product_id: str,
                  body: Annotated[ApproveIn | None, Body()] = None,
                  x_approve_code: Annotated[str | None, Header()] = None):
    ctx = _ctx(request)
    rt = ctx.rt
    _chef(ctx, request, f"steady:{order_id}:{product_id}", x_approve_code, body)
    with rt.lock:
        live = rt.live()
        so, _h = _get_order(order_id)
        state = _load(live.path, so.id)
        if not state:
            raise HTTPException(409, "Renew the order first.")
        view = _view(state)
        idx = next((i for i, ln in enumerate(view.lines) if ln.product_id == product_id), None)
        if idx is None:
            raise HTTPException(404, f"No line {product_id} in {so.id}.")
        line = view.lines[idx]
        if line.result not in (str(LineResult.WAITING), str(LineResult.FLAGGED)) or not line.this_week_quantity:
            raise HTTPException(409, f"Line {product_id} is {line.result}, only a waiting or flagged line "
                                     "can be accepted.")
        mandate = _pass(live.path, live.keys)
        diet = {ln.product_id: ln.diet for ln in so.lines}[product_id]
        delivery = date.fromisoformat(state["delivery"])
        try:
            if line.order_id:  # renewed, then Valio's second answer made it wait: approve that order, no second one
                o = live.service.get(line.order_id)
            else:
                order_lines, base = _accept_lines(line)
                # a placed order gets this approval entry just before its own, cause before effect
                note = (f"Owner accepted {_qty_of(line.this_week_quantity, product_id)} for Steady Order {so.id}: "
                        f"{line.sentence}")
                o = live.service.submit(
                    mandate=mandate, lines=order_lines, deliver_by=delivery,
                    idempotency_key=f"steady:{so.id}:{delivery}:{product_id}:accept", actor=CHEF, accepted_by=CHEF,
                    accept_note=note, required_claims=diet, split_base_cents=base)
            if o["state"] == "waiting":  # approve writes the approval entry, then the order entry
                o = live.service.approve(o["id"], CHEF, verb="accepted")  # Valio asked again, a block is never lifted
        except ApproveRefused as e:
            # no waiting order is left behind where no page shows it: the line ends blocked with the reason
            o = live.service.reject(o["id"], "validio", reason="approval refused")
            _refuse(live.path, so.id, state, view, idx, str(e), o["id"])
        except OrderError as e:
            raise HTTPException(409, str(e)) from e
        if o["state"] != "placed":
            _refuse(live.path, so.id, state, view, idx, o["decision"]["sentence"], o["id"])
        lines = list(view.lines)
        lines[idx] = line.model_copy(update={"result": str(LineResult.ACCEPTED), "accept_label": None,
                                             "order_id": o["id"], "total_cents": o["totalCents"]})
        view = view.model_copy(update={"lines": lines})
        _save(live.path, so.id, {**state, "view": _dump(view)})
        return _with_pass(view, live)

