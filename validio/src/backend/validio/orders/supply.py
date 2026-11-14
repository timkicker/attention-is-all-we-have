"""request_supply and confirm_order: one request from the agent's text to a decision.

Text or typed lines become a typed need, the static catalog narrows it to at most 12 candidates,
Valio is asked only about those (and Safe Swap's few substitutes), every option gets its Fact Grades,
Best Pick ranks, Cedar decides per option. Nothing the agent says about price or trust is read.
"""

import logging
import re
import sqlite3
import time
from collections import Counter
from dataclasses import dataclass
from datetime import date
from typing import Any

from ..catalog.model import Product
from ..matching import compare
from ..matching.need import CLAIM_NAMES, KINDS, Need, Ranked, parse_need, screen
from ..matching.rank import rank
from ..matching.reasons import carbon_sentence, option_sentence
from ..matching.substitute import SubOption, SubVerdict, safe_swap
from ..policy.decide import Outcome, context_for, decide
from ..policy.mandate import Mandate
from ..text.format import money, qty_of, short_ref
from ..valio.budget import CallBudget, CallBudgetExceeded
from ..valio.client import NotRecorded, ReplayMiss, ValioBusy, ValioRefused, ValioUnavailable, days_text
from .explain import explain
from .service import (
    SEVERITY,
    IdempotencyConflict,
    LineIn,
    OrderError,
    OrderService,
    _hash,
    fact_dict,
    mandate_dict,
)
from .store import NotFound

ACCEPTED = ("chosen", "ranked")  # the only verdicts an agent may confirm

NEAR = {"FREE_FROM_LACTOSE": "LOW_LACTOSE"}


def _why_none(b: dict) -> str:
    """Why a line has no option, in one sentence: what Valio does not have, or the reason most of its options
    were turned down, the Spend Pass rules first since those options were otherwise fine."""
    from ..api.display import group, reasons

    need, options = b["need"], b["line"]["options"]
    what = need.kind.replace("_", " ") or "it"
    if not options:
        return f"Valio has no {_none_of(need)}."
    blocked = [o for o in options if o["verdict"] == "blocked"] or options
    heads = Counter(group(reasons(o["sentence"]))[0] for o in blocked)
    head = heads.most_common(1)[0][0]
    if head == "Over the hard cap":  # the cheapest that broke it, so the gap is never overstated
        caps = [(int(m.group(1).replace(",", "").replace(".", "")), m.group(1), m.group(2)) for o in blocked
                if (m := re.search(r"([\d,.]+) € is over the hard cap of ([\d,.]+ €)", o["sentence"]))]
        if caps:
            _, total, cap = min(caps)
            return f"Blocked: {total} € is over the {cap} never-above limit."
    if head == "Outside the pass's product groups":
        return f"Blocked: {what} is outside the Spend Pass's product groups."
    if head.startswith("Not ") and head[4:] in {v for v in CLAIM_NAMES.values()}:
        return f"No plain {head[4:].replace(' ', '-')} {what} at Valio."
    return f"No {what} can be ordered: {head[0].lower()}{head[1:]}."


def _none_of(need: Need) -> str:
    """"lactose-free parmesan", for "Valio has no ..."."""
    diet = " ".join(CLAIM_NAMES.get(c, c).replace(" ", "-") for c in sorted(need.required_claims))
    return f"{diet} {need.kind.replace('_', ' ')}".strip()


def not_recorded_day(day: date, days: list[date]) -> str:
    """The 503 for a delivery day without recordings: names the days that have them, so an agent can pick one."""
    have = f" Recorded delivery days: {days_text(days)}." if days else ""
    return f"Valio's answers for delivery on {day:%a} {day.isoformat()} aren't recorded for this demo.{have} Nothing was ordered."


@dataclass(frozen=True)
class LineRequest:
    text: str | None = None
    product_id: str | None = None
    quantity: float | None = None
    unit: str | None = None  # the product's sales unit, or L / KG


def order_status(o: dict) -> str:
    """The request status an order's state gives."""
    return {"placed": "ordered" if o.get("approvedBy") else "ordered_alone",
            "waiting": "waiting", "rejected": "rejected", "blocked": "blocked"}[o["state"]]


class RequestError(ValueError):
    """The request cannot be read (HTTP 422)."""


def _sentence(r: Ranked, carbon: str | None = None) -> str:
    """`carbon` is the footprint sentence the line's note already gives for every option, left out here."""
    return option_sentence(r.why, r.reasons, r.notes, r.accepted, carbon)


def _kind_of(p: Product) -> str | None:
    name = (p.name_en or "").lower()
    return next((k for k, v in KINDS.items() if any(w in name for w in v.words)), None)


class SupplyService:
    def __init__(self, orders: OrderService, reader=None):
        self.orders = orders
        self.store, self.catalog, self.audit = orders.store, orders.catalog, orders.audit
        self.reader = reader  # (text, product_id) -> ReaderResult, injected so this module never imports it
        self._readings: dict[tuple[str, str], dict] = {}

    @property
    def valio(self):
        return self.orders.valio

    def now(self):
        return self.orders.clock()

    # building the typed need

    def _need(self, ln: LineRequest, mandate: Mandate, deliver_by: date | None) -> Need:
        diet = set(mandate.diet or ())
        if ln.product_id:
            p = self.catalog.get(ln.product_id)
            if p is None:
                raise RequestError(f"unknown product {ln.product_id}")
            if not ln.quantity or ln.quantity <= 0:
                raise RequestError("a product line needs a positive quantity")
            unit = (ln.unit or p.sales_unit).upper()
            unit = unit if unit in ("L", "KG") else "PCS"
            need = Need(_kind_of(p) or "", ln.quantity, unit, set(diet), set(), deliver_by or self._default_by(mandate),
                        None, product_id=p.id,
                        text=ln.text or qty_of(ln.quantity, p, ln.unit))
        elif ln.text:
            try:
                need = parse_need(ln.text, self.now().date(), self.catalog)
            except ValueError as e:
                raise RequestError(str(e)) from e
            need.required_claims |= diet
            if deliver_by:
                need.deliver_by = deliver_by
        else:
            raise RequestError("a line needs text or a product id")
        need.excluded_claims |= {NEAR[c] for c in need.required_claims if c in NEAR}
        return need

    def _line_text(self, ln: LineRequest) -> str:
        p = self.catalog.get(ln.product_id) if ln.product_id else None
        if ln.text or p is None:
            return ln.text or f"{ln.quantity:g} {ln.unit or ''} of {ln.product_id}"
        return qty_of(ln.quantity or 0, p, ln.unit)

    def _default_by(self, mandate: Mandate) -> date:
        return date.fromisoformat(mandate.deliver_by) if mandate.deliver_by else self.now().date()

    # options as the web app and the agent see them

    def _supplier_text(self, p: Product) -> dict | None:
        if not (p.marketing_en or p.planted_en):
            return None
        out: dict[str, Any] = {"text": p.planted_en or p.marketing_en, "grade": "untrusted",
                               "planted": bool(p.planted_en)}
        if p.planted_en and self.reader is not None:
            # display only: the reading goes to the screen and never back into ranking or rules
            key = (p.id, p.planted_en)
            if key not in self._readings:
                self._readings[key] = self.reader(p.planted_en, p.id).model_dump()
            out["reader"] = self._readings[key]
        return out

    def _option(self, r: Ranked, verdict: str, sentence: str, rank_no: int | None = None,
                on_list: bool | None = None, substitute: bool = False) -> dict:
        p = r.product
        o = {"productId": p.id, "name": p.name_en, "verdict": verdict, "sentence": sentence,
             "facts": [fact_dict(f) for f in r.facts], "isSubstitute": substitute}
        if rank_no is not None:
            o["rank"] = rank_no
        if r.sales_qty is not None:
            o["quantity"], o["unit"] = r.sales_qty, p.sales_unit
        if r.total_cents is not None:
            o["totalCents"] = r.total_cents
        o["reliabilityText"] = compare.reliability_text(p)
        if on_list is not None:
            o["onValioList"] = on_list
        if st := self._supplier_text(p):
            o["supplierText"] = st
        return o

    def _judge(self, mandate: Mandate, r: Ranked, avail, **flags) -> Any:
        if r.total_cents is None:
            return None
        ctx = context_for(mandate, r.product, avail, total_cents=r.total_cents, now=self.now(), **flags)
        return decide(ctx, product_id=r.product.id)

    def _line(self, ln: LineRequest, mandate: Mandate, deliver_by: date | None, budget: CallBudget,
              n: int) -> dict:
        need = self._need(ln, mandate, deliver_by)
        cands, dropped = screen(need, self.catalog)
        ids = [p.id for p in cands]
        self.orders.check_valio()  # the demo switch "Valio not answering"
        try:
            quotes = self.valio.price(ids, need.deliver_by, budget) if ids else {}
            avail = self.orders.adjust(self.valio.availability(ids, need.deliver_by, budget)) if ids else {}
        except NotRecorded:
            raise
        except ReplayMiss as e:
            logging.getLogger(__name__).warning("replay miss: %s", e)  # ids and the fix, for the developer
            p = self.catalog.get(need.product_id) if need.product_id else None
            days = getattr(self.valio, "recorded_days", lambda: None)()
            if days is not None and need.deliver_by not in days:
                raise NotRecorded(not_recorded_day(need.deliver_by, days)) from e
            what = short_ref(p.name_en) if p else need.kind.replace("_", " ") or "these products"
            raise NotRecorded(f"Valio's answers for {what} aren't recorded for this demo. Nothing was ordered.") from e
        ranked = rank(need, cands, quotes, avail, self.now(), prefer_labels=tuple(mandate.prefer_labels or ()))

        carbon = {p.carbon_kg_per_kg for p in cands if p.carbon_kg_per_kg is not None}
        same = carbon_sentence(next(p for p in cands if p.carbon_kg_per_kg is not None)) if len(cands) > 1 and len(carbon) == 1 else None
        options, chosen = [], None
        for r in ranked:
            d = self._judge(mandate, r, avail.get(r.product.id))
            denied = d is not None and d.outcome is Outcome.DENY
            if r.accepted and not denied and chosen is None:
                chosen = r
                options.append(self._option(r, "chosen", _sentence(r, same), 1))
            elif r.accepted and not denied:
                options.append(self._option(r, "ranked", _sentence(r, same),
                                            len([o for o in options if "rank" in o]) + 1))
            elif denied:
                options.append(self._option(r, "blocked", f"{_sentence(r, same)} {d.sentence}"))
            else:
                verdict = "not_deliverable" if "Valio gives no delivery date for it" in r.reasons else "rejected"
                options.append(self._option(r, verdict, _sentence(r, same)))
        options += [self._option(r, "rejected", _sentence(r)) for r in dropped]
        decided = self._compare(need, ranked, options, chosen, quotes, avail, mandate)

        line: dict[str, Any] = {
            "lineId": f"L-{n}", "text": need.text,
            "need": {"what": need.kind.replace("_", " ") or "product", "quantity": need.quantity, "unit": need.unit,
                     "diet": [CLAIM_NAMES.get(c, c) for c in sorted(need.required_claims)],
                     "deliverBy": need.deliver_by.isoformat(), "productId": need.product_id},
            "options": options,
        }
        proposal = None
        if chosen is not None:
            proposal = LineIn(chosen.product.id, chosen.sales_qty)
        elif need.product_id:
            original = self.catalog.get(need.product_id)
            sw = safe_swap(original, need, self.catalog, self.valio, need.deliver_by, budget, self.now(),
                           search_outside=bool(need.kind))
            line["substitutes"] = [self._sub(o) for o in sw.listed]
            if sw.searched_outside:
                line["beyondList"] = [self._sub(o) for o in sw.outside]
            line["swapSentence"] = sw.sentence
            if (best := sw.best) is not None:
                for o in line.get("substitutes", []) + line.get("beyondList", []):
                    if o["productId"] == best.product.id:
                        o["verdict"], o["rank"] = "chosen", 1
                proposal = LineIn(best.product.id, best.ranked.sales_qty, is_substitute=True,
                                  on_valio_list=best.on_valio_list)
        if any((o.get("supplierText") or {}).get("planted") for o in options):
            line["note"] = "A description in these options talks to AI agents. Descriptions are never used for decisions."
        if same:
            line["note"] = f"Same footprint for all: {carbon.pop():g} kg CO2e per kg, a group average."
        if decided:
            line["decidedBy"] = decided
            line["decidedByText"] = "Only one option fits." if decided == "only option" else f"Decided by: {decided}."
        return {"line": line, "proposal": proposal, "need": need}

    def _compare(self, need: Need, ranked: list[Ranked], options: list[dict], chosen: Ranked | None, quotes,
                 avail, mandate: Mandate) -> str | None:
        """The comparison rows of every ranked option and why the chosen one won (matching/compare.py).
        Returns the key that decided, None when nothing was chosen."""
        by_id = {o["productId"]: o for o in options}
        now = self.now()
        unit: dict[int, str | None] = {}
        for r in ranked:
            o = by_id.get(r.product.id)
            if o is None:
                continue
            a = avail.get(r.product.id)
            unit[id(r)] = compare.unit_price_text(compare.unit_price_cents(need, r, quotes.get(r.product.id)),
                                                  need.unit)
            extra = {"unitPriceText": unit[id(r)], "deliveryText": compare.delivery_text(a, need.deliver_by),
                     "deliveryDate": a.delivery_on(need.deliver_by).isoformat() if a is not None and a.lines else None,
                     "cutoffText": compare.cutoff_text(a, now),
                     "dietText": compare.diet_text(r.product, need.required_claims)}
            o.update({k: v for k, v in extra.items() if v is not None})
        if chosen is None:
            return None
        ok = [r for r in ranked if by_id.get(r.product.id, {}).get("verdict") in ACCEPTED
              and r.total_cents is not None]
        cheapest = min(r.total_cents for r in ok)
        prefer = tuple(mandate.prefer_labels or ())
        runner = next((r for r in ok if r is not chosen), None)
        decided = compare.decided_by(chosen, runner, cheapest, prefer)
        by_id[chosen.product.id]["whyText"] = compare.why_text(chosen, runner, decided, cheapest, unit)
        for r in ok:
            if r is not chosen:
                by_id[r.product.id]["whyNotText"] = compare.why_not_text(r, chosen, cheapest, unit, prefer)
        return decided

    def _sub(self, o: SubOption) -> dict:
        verdict = {SubVerdict.BLOCKED_DIET: "blocked", SubVerdict.UNDELIVERABLE: "not_deliverable",
                   SubVerdict.REJECTED: "rejected"}.get(o.verdict, "ranked")
        if o.ranked is None:
            p = o.product
            out = {"productId": p.id, "name": p.name_en, "verdict": verdict, "sentence": o.sentence + ".",
                   "facts": [], "onValioList": o.on_valio_list, "isSubstitute": True}
            if st := self._supplier_text(p):
                out["supplierText"] = st
            return out
        why = _sentence(o.ranked) if verdict == "ranked" else ""
        sentence = o.sentence + "." + (f" {why}" if why else "")
        return self._option(o.ranked, verdict, sentence, on_list=o.on_valio_list, substitute=True)

    # the two agent calls

    def request_supply(self, *, mandate: Mandate, lines: list[LineRequest], deliver_by: date | None,
                       idempotency_key: str, agent: str | None = None, text: str | None = None) -> dict:
        if not lines:
            raise RequestError("a request needs at least one line")
        if len(lines) > 10:
            raise RequestError("at most 10 lines per request")
        body_hash = _hash({"lines": [(ln.text, ln.product_id, ln.quantity, ln.unit) for ln in lines],
                           "deliverBy": deliver_by.isoformat() if deliver_by else None})
        with self.orders.lock, self.store.tx():
            self.orders.check_open()
            seen = self.store.idem_get(mandate.id, "request:" + idempotency_key)
            if seen:
                if seen[0] != body_hash:
                    raise IdempotencyConflict("this idempotency key was used for another request")
                return self.get_request(seen[1])
            self.store.remember_pass(mandate.id, mandate_dict(mandate))
            budget = CallBudget(self.orders.max_ids)
            started = time.monotonic()
            remember = True  # Valio not answering is never remembered, so the same key can try again
            req = self.store.new_request({"createdAt": self.orders.stamp().isoformat(), "agent": agent or mandate.holder,
                                          "text": text or "; ".join(self._line_text(ln) for ln in lines),
                                          "spendPassId": mandate.id, "status": "working"})
            self._log(req, mandate, agent or mandate.holder, "request",
                      f"The agent asked for {req['text']}.", [], None)
            try:
                built = [self._line(ln, mandate, deliver_by, budget, i + 1) for i, ln in enumerate(lines)]
                req["lines"] = [b["line"] for b in built]
                req["deliverBy"] = min(b["need"].deliver_by for b in built).isoformat()
                proposals = [b["proposal"] for b in built if b["proposal"] is not None]
                missing = [b["line"]["lineId"] for b in built if b["proposal"] is None]
                for b in built:
                    if (p := b["proposal"]) is not None:
                        b["line"]["chosen"] = {"productId": p.product_id, "salesQty": p.sales_qty,
                                               "isSubstitute": p.is_substitute, "onValioList": p.on_valio_list}
                for b in built:
                    for o in b["line"]["options"]:
                        if (o.get("supplierText") or {}).get("planted"):
                            self._log(req, mandate, "validio", "decision",
                                      f"Ignored the description of {short_ref(o['name'])}, "
                                      f"which talks to AI agents. "
                                      f"Descriptions are never used for decisions. {o['sentence']}", [], None)
                if missing and not proposals:
                    # a line with no product at all says what Valio does not have, not that rules were broken
                    # each line says its leading reason, not that rules were broken somewhere
                    sentence = " ".join(_why_none(b) for b in built if b["proposal"] is None) + " Nothing was ordered."
                    req["decision"] = {"outcome": "block", "ruleIds": [], "sentence": sentence}
                    req["status"] = "blocked"
                    self._log(req, mandate, "validio", "decision", req["decision"]["sentence"], [], None)
                else:
                    # Cedar over the whole proposal, with totals Valio gives for the summed order
                    quoted = self.orders.quote(proposals, date.fromisoformat(req["deliverBy"]), budget=budget)
                    stated = [b["need"].budget_cents for b in built if b["need"].budget_cents]
                    req["budgetCents"] = sum(stated) if stated else None
                    decision = self.orders._decide(mandate, quoted, budget_cents=req["budgetCents"])
                    if missing:
                        decision = {**decision, "outcome": max(decision["outcome"], "ask_human", key=SEVERITY.get),
                                    "sentence": decision["sentence"] + f" No safe option for {', '.join(missing)}."}
                    req["decision"] = decision
                    req["totalCents"] = sum(q["totalCents"] or 0 for q in quoted)
                    req["proposal"] = [{"productId": p.product_id, "salesQty": p.sales_qty,
                                        "isSubstitute": p.is_substitute, "onValioList": p.on_valio_list}
                                       for p in proposals]
                    if decision["outcome"] == "auto_order":
                        req["status"] = "working"
                        self._log(req, mandate, "validio", "decision", decision["sentence"], decision["ruleIds"], None)
                    elif decision["outcome"] == "ask_human":
                        o = self.orders.submit(mandate=mandate, lines=proposals, deliver_by=date.fromisoformat(
                            req["deliverBy"]), idempotency_key="request:" + req["id"], request_id=req["id"],
                            actor=agent, budget=budget, budget_cents=req["budgetCents"])
                        req["orderId"] = o["id"]
                        req["status"] = "waiting"
                        req["question"] = self._question(built, o)
                    else:
                        req["status"] = "blocked"
                        self._log(req, mandate, "validio", "decision", decision["sentence"], decision["ruleIds"], None)
            except ValioUnavailable as e:
                # Valio did not answer twice (or is busy, or refused the key): refused before any order, one
                # entry in the ledger, and not remembered under the key, so a retry after Valio is back works
                req["lines"], req["status"] = [], "blocked"
                said = str(e) if isinstance(e, (ValioBusy, ValioRefused)) else \
                    f"Valio didn't answer at {self.orders.stamp():%H:%M}. Nothing was ordered."
                req["decision"] = {"outcome": "block", "ruleIds": [], "sentence": str(e),
                                   "reasonCode": "valio_down", "ownerText": said}
                self._log(req, mandate, "validio", "decision", str(e), [], None)
                remember = False
            except (RequestError, CallBudgetExceeded, OrderError) as e:
                # refused before a decision: stored as blocked, with the reason in the ledger
                req["lines"], req["status"] = [], "blocked"
                why = str(e).strip(chr(39))
                if isinstance(e, CallBudgetExceeded):
                    code = "too_many"
                    said = "This request needs more products checked than Validio asks Valio at once. Nothing was ordered."
                else:
                    code, said = "unreadable", f"Validio couldn't use this request: {why}. Nothing was ordered."
                req["decision"] = {"outcome": "block", "ruleIds": [],
                                   "sentence": f"Refused the request: {why}. Nothing was ordered.",
                                   "reasonCode": code, "ownerText": said}
                self._log(req, mandate, "validio", "decision", req["decision"]["sentence"], [], None)
            req["liveChecked"] = {"calls": budget.calls, "ids": budget.ids_sent, "idsPerCall": budget.per_call}
            req["elapsedMs"] = round((time.monotonic() - started) * 1000)
            if (mode := getattr(self.valio, "mode", None)) in ("live", "record", "replay"):
                req["valioMode"] = mode
            self.store.put_request(req)
            if remember:
                self.store.idem_put(mandate.id, "request:" + idempotency_key, body_hash, req["id"])
            return self.get_request(req["id"])

    def _question(self, built: list[dict], order: dict) -> str:
        """Only the question: why it waits is the swap sentence and the decision, shown next to it."""
        return f"Order {self.orders._parts(order, ids=False)} for {money(order['totalCents'])}?"

    def confirm_order(self, *, mandate: Mandate, request_id: str, choice: list[tuple[str, int]],
                      idempotency_key: str, agent: str | None = None) -> dict:
        """One request gives at most one order: the whole call runs under the service lock, and the store
        refuses a second order for the same request even from another process."""
        with self.orders.lock, self.store.tx():
            self.orders.check_open()
            req = self.store.request(request_id)
            if req is None:
                raise NotFound(f"no request {request_id}")
            if req["spendPassId"] != mandate.id:
                raise OrderError("this request belongs to another Spend Pass")
            if req.get("orderId"):
                return self.orders.get(req["orderId"])
            if (done := self.store.order_for_request(request_id)) is not None:
                return done
            if req["status"] != "working":
                raise OrderError(f"request {request_id} is {req['status']}, nothing to confirm")
            allowed: dict[str, dict] = {}
            refused: dict[str, str] = {}
            for ln in req["lines"]:
                for o in ln["options"] + ln.get("substitutes", []) + ln.get("beyondList", []):
                    if o["verdict"] in ACCEPTED:
                        allowed[o["productId"]] = o
                    else:
                        refused.setdefault(o["productId"], f"{o['verdict']} for this request: {o['sentence']}")
            lines, seen = [], set()
            for pid, qty in choice:
                if pid in seen:
                    raise OrderError(f"{pid} is in the choice twice, send one line with the whole amount")
                seen.add(pid)
                if pid not in allowed:
                    raise OrderError(f"{pid} was {refused[pid]}" if pid in refused and pid not in allowed
                                     else f"{pid} is not one of the options of {request_id}")
                o = allowed[pid]
                lines.append(LineIn(pid, int(qty), bool(o.get("isSubstitute")), bool(o.get("onValioList"))))
            try:
                o = self.orders.submit(mandate=mandate, lines=lines, deliver_by=date.fromisoformat(req["deliverBy"]),
                                       idempotency_key=idempotency_key, request_id=request_id, actor=agent,
                                       budget_cents=req.get("budgetCents"))
            except sqlite3.IntegrityError:  # another process placed the order for this request first
                return self.store.order_for_request(request_id)
            req["orderId"] = o["id"]
            self.store.put_request(req)
            return o

    def get_request(self, request_id: str) -> dict:
        req = self.store.request(request_id)
        if req is None:
            raise NotFound(f"no request {request_id}")
        req["requestId"] = req["id"]
        source = req.get("decision")  # what decided, before the sentence below says what happened last
        if req.get("orderId"):
            o = self.orders.get(req["orderId"])
            req["status"] = order_status(o)
            source = o["decision"]
            if o["state"] in ("placed", "blocked") or o.get("approvedBy"):
                req["decision"] = {**req.get("decision", {}), "sentence": self._latest_sentence(o)
                                   or req.get("decision", {}).get("sentence", "")}
            req["totalCents"] = o["totalCents"]
        if req.get("decision"):
            diet = sorted({d for ln in req.get("lines") or [] for d in ln["need"]["diet"]})
            req["decision"] = {**req["decision"], **explain(source, req["status"], diet, req.get("deliverBy"))}
        return req

    def _latest_sentence(self, o: dict) -> str | None:
        entries = self.audit.list(order_id=o["id"])
        return entries[-1].sentence if entries else None

    def _log(self, req, mandate, actor, kind, sentence, rule_ids, order_id) -> None:
        self.audit.append(at=self.orders.stamp(), actor=actor, kind=kind, sentence=sentence, facts=[],
                          mandate_id=mandate.id, disclosed=mandate.disclosed, rule_ids=rule_ids, order_id=order_id)


