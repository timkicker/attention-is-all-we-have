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
import sqlite3
import threading
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Body, Header, HTTPException
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from ..audit.log import AuditLog
from ..catalog.store import Catalog
from ..config import load_settings
from ..demo import seed
from ..orders.service import ApproveRefused, LineIn, OrderError, OrderService
from ..orders.store import Store
from ..standing.drift import unit_word
from ..standing.learn import learn
from ..standing.model import LineResult, RenewedLine, StandingOrder
from ..standing.renew import run
from ..valio.client import ValioClient
from .schemas import ApproveIn

router = APIRouter(prefix="/api/steady", tags=["steady"])
ACTOR = "validio:steady-order"
CHEF = "kitchen:chef"
WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
STATE_SCHEMA = "create table if not exists steady_state (order_id text primary key, body text not null)"


class Camel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


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


class SplitOut(Camel):
    parts: list[SplitPartOut]
    total_cents: int
    extra_cost_cents: int
    extra_cost_pct: float


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


class SteadyOrderOut(Camel):
    id: str
    name: str
    weekday: str
    guests_per_week: int
    weeks_learned: int
    simulated_history: bool
    renewed_at: str | None = None
    lines: list[SteadyLineOut]


class SteadyOrderSummaryOut(Camel):
    id: str
    name: str
    weekday: str
    line_count: int
    flag_count: int
    renewed_at: str | None = None


@dataclass
class _Live:
    token: str
    path: Path
    store: Store
    audit: AuditLog
    service: OrderService


class Runtime:
    """Catalog and Valio once, the stores per seed. A new seed token (after `make seed`) reopens them."""

    def __init__(self):
        self.lock = threading.RLock()
        self._live: _Live | None = None
        self._catalog: Catalog | None = None
        self._valio: ValioClient | None = None

    @property
    def settings(self):
        return load_settings()

    @property
    def catalog(self) -> Catalog:
        if self._catalog is None:
            self._catalog = Catalog(self.settings.catalog_db)
        return self._catalog

    @property
    def valio(self) -> ValioClient:
        if self._valio is None:
            s = self.settings
            self._valio = ValioClient(s.valio_base_url, s.valio_api_key, s.valio_mode, s.valio_cache,
                                      customer=s.valio_customer)
        return self._valio

    def live(self) -> _Live:
        path = seed.db_path()
        token = seed.seed_token(path)
        if token is None:
            seed.reset(path)
            token = seed.seed_token(path)
        if self._live is None or (self._live.token, self._live.path) != (token, path):
            if self._live is not None:
                self._live.store.close()
            store, audit = Store(path), AuditLog(path)
            service = OrderService(store, self.catalog, self.valio, audit, clock=lambda: self.settings.now,
                                   adjust=lambda avail: seed.apply_stockout(avail, seed.stockout(path)))
            self._live = _Live(token, path, store, audit, service)
        return self._live


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


def _chef(key: str, header: str | None, body) -> None:
    # the approve route's code check, imported late: api.state imports this module
    from .state import get_ctx
    from .ui import _code

    _code(get_ctx(), key, header, body)


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
            sentence=f"Median of the last {len(amounts)} weeks." if varies else "Usual amount.",
            history=amounts if varies else None))
    return SteadyOrderOut(id=so.id, name=so.name, weekday=WEEKDAY_NAMES[so.weekday], guests_per_week=so.guests,
                          weeks_learned=so.learned_from, simulated_history=so.simulated, lines=out)


_UNITS: dict[str, str] = {}


def _unit(pid: str) -> str:
    # the sales unit from the catalog in the words a chef reads
    if pid not in _UNITS:
        p = runtime.catalog.get(pid)
        su = p.sales_unit if p else ""
        _UNITS[pid] = {"BAG": "bags", "KI": "cartons", "ST": "packs"}.get(su, (su or "units").lower())
    return _UNITS[pid]


def _line_out(pending: SteadyLineOut, rl: RenewedLine) -> SteadyLineOut:
    split = None
    if rl.result is LineResult.SPLIT_RENEWED and rl.split is not None:
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


def _view(state: dict) -> SteadyOrderOut:
    return SteadyOrderOut.model_validate(state["view"])


def _dump(view: SteadyOrderOut) -> dict:
    return view.model_dump(by_alias=False)


@router.get("", response_model=list[SteadyOrderSummaryOut], response_model_exclude_none=True)
def steady_list():
    with runtime.lock:
        live = runtime.live()
        so, h = _steady()
        state = _load(live.path, so.id)
        view = _view(state) if state else _pending(so, h)
    flagged = [ln for ln in view.lines if ln.flags and ln.result != "accepted"]
    return [SteadyOrderSummaryOut(id=view.id, name=view.name, weekday=view.weekday, line_count=len(view.lines),
                                  flag_count=len(flagged), renewed_at=view.renewed_at)]


@router.get("/{order_id}", response_model=SteadyOrderOut, response_model_exclude_none=True)
def steady_order(order_id: str):
    with runtime.lock:
        live = runtime.live()
        so, h = _get_order(order_id)
        state = _load(live.path, so.id)
        return _view(state) if state else _pending(so, h)


@router.post("/{order_id}/renew", response_model=SteadyOrderOut, response_model_exclude_none=True)
def steady_renew(order_id: str, body: Annotated[ApproveIn | None, Body()] = None,
                 x_approve_code: Annotated[str | None, Header()] = None):
    _chef(f"steady:{order_id}", x_approve_code, body)
    with runtime.lock:
        live = runtime.live()
        so, h = _get_order(order_id)
        state = _load(live.path, so.id)
        if state:  # already renewed this week: nothing is ordered twice
            return _view(state)
        s = runtime.settings
        mandate = seed.spend_pass(live.path, now=s.now)
        renewal = run(so, h, runtime.catalog, runtime.valio, mandate, s.now, stockout=seed.stockout(live.path))
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
                    at=s.now, actor="validio", kind="decision",
                    sentence=f"Steady Order {so.id}, {rl.usual_qty} {line.unit} of {rl.product_id} "
                             f"{line.name}: {rl.sentence}" + (f" {flags}" if flags else ""),
                    facts=[], mandate_id=mandate.id, disclosed=mandate.disclosed,
                    rule_ids=list(rl.decision.rule_ids) if rl.decision is not None else [], order_id=None)
            out.append(line)
        view = _pending(so, h).model_copy(update={"lines": out, "renewed_at": s.now.isoformat()})
        _save(live.path, so.id, {"view": _dump(view), "delivery": renewal.delivery.isoformat()})
        return view


@router.post("/{order_id}/lines/{product_id}/accept", response_model=SteadyOrderOut,
             response_model_exclude_none=True)
def steady_accept(order_id: str, product_id: str, body: Annotated[ApproveIn | None, Body()] = None,
                  x_approve_code: Annotated[str | None, Header()] = None):
    _chef(f"steady:{order_id}:{product_id}", x_approve_code, body)
    with runtime.lock:
        live = runtime.live()
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
        s = runtime.settings
        mandate = seed.spend_pass(live.path, now=s.now)
        diet = {ln.product_id: ln.diet for ln in so.lines}[product_id]
        delivery = date.fromisoformat(state["delivery"])
        try:
            o = live.service.submit(
                mandate=mandate, lines=[LineIn(product_id, line.this_week_quantity)], deliver_by=delivery,
                idempotency_key=f"steady:{so.id}:{delivery}:{product_id}:accept", actor=CHEF,
                required_claims=diet)
            if o["state"] == "waiting":
                o = live.service.approve(o["id"], CHEF)  # Valio asked again, a block is never lifted
            elif o["state"] == "placed":  # approve writes its own approval entry, this path needs one
                live.audit.append(
                    at=s.now, actor=CHEF, kind="approval",
                    sentence=f"Chef accepted {line.this_week_quantity} {line.unit} of {product_id} {line.name} "
                             f"for Steady Order {so.id}: {line.sentence}",
                    facts=[], mandate_id=mandate.id, disclosed=mandate.disclosed, rule_ids=[], order_id=o["id"])
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
        return view

