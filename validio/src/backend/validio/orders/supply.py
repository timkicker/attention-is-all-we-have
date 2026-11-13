"""request_supply and confirm_order: one request from the agent's text to a decision.

Text or typed lines become a typed need, the static catalog narrows it to at most 12 candidates,
Valio is asked only about those (and Safe Swap's few substitutes), every option gets its Fact Grades,
Best Pick ranks, Cedar decides per option. Nothing the agent says about price or trust is read.
"""

import sqlite3
from dataclasses import dataclass
from datetime import date
from typing import Any

from ..catalog.model import Product
from ..matching.need import CLAIM_NAMES, KINDS, Need, Ranked, parse_need, screen
from ..matching.rank import rank
from ..matching.substitute import SubOption, SubVerdict, safe_swap
from ..policy.decide import Outcome, context_for, decide
from ..policy.mandate import Mandate
from ..valio.budget import CallBudget, CallBudgetExceeded
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


@dataclass(frozen=True)
class LineRequest:
    text: str | None = None
    product_id: str | None = None
    quantity: float | None = None
    unit: str | None = None  # the product's sales unit, or L / KG


class RequestError(ValueError):
    """The request cannot be read (HTTP 422)."""


def _sentence(r: Ranked) -> str:
    parts = list(r.why) if r.accepted and r.why else list(r.reasons) + list(r.notes)
    s = "; ".join(p for p in parts if p) or "Not usable"
    return s[0].upper() + s[1:] + ("" if s.endswith(".") else ".")


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
                        None, product_id=p.id, text=ln.text or f"{ln.quantity:g} {ln.unit or p.sales_unit} of {p.id}")
        elif ln.text:
            try:
                need = parse_need(ln.text, self.now().date())
            except ValueError as e:
                raise RequestError(str(e)) from e
            need.required_claims |= diet
            if deliver_by:
                need.deliver_by = deliver_by
        else:
            raise RequestError("a line needs text or a product id")
        need.excluded_claims |= {NEAR[c] for c in need.required_claims if c in NEAR}
        return need

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
        quotes = self.valio.price(ids, need.deliver_by, budget) if ids else {}
        avail = self.orders.adjust(self.valio.availability(ids, need.deliver_by, budget)) if ids else {}
        ranked = rank(need, cands, quotes, avail, self.now(), prefer_labels=tuple(mandate.prefer_labels or ()))

        options, chosen = [], None
        for r in ranked:
            d = self._judge(mandate, r, avail.get(r.product.id))
            denied = d is not None and d.outcome is Outcome.DENY
            if r.accepted and not denied and chosen is None:
                chosen = r
                options.append(self._option(r, "chosen", _sentence(r), 1))
            elif r.accepted and not denied:
                options.append(self._option(r, "ranked", _sentence(r), len([o for o in options if "rank" in o]) + 1))
            elif denied:
                options.append(self._option(r, "blocked", f"{_sentence(r)[:-1]}. {d.sentence}"))
            else:
                verdict = "not_deliverable" if "Valio gives no delivery date for it" in r.reasons else "rejected"
                options.append(self._option(r, verdict, _sentence(r)))
        options += [self._option(r, "rejected", _sentence(r)) for r in dropped]

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
        carbon = {p.carbon_kg_per_kg for p in cands if p.carbon_kg_per_kg is not None}
        if len(cands) > 1 and len(carbon) == 1:
            line["note"] = (f"All these products have the same footprint in Valio's data ({carbon.pop():g} kg CO2e "
                            f"per kg, a group average), so it does not change the choice.")
        return {"line": line, "proposal": proposal, "need": need}

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
            now = self.now()
            req = self.store.new_request({"createdAt": now.isoformat(), "agent": agent or mandate.holder,
                                          "text": text or "; ".join(ln.text or f"{ln.quantity:g} {ln.unit or ''} "
                                                                   f"of {ln.product_id}" for ln in lines),
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
                                      f"Ignored the description of {o['productId']}, which talks to AI agents. "
                                      f"Descriptions are never used for decisions. {o['sentence']}", [], None)
                if missing and not proposals:
                    req["decision"] = {"outcome": "block", "ruleIds": [],
                                       "sentence": "No option keeps every rule and can be delivered, nothing was ordered."}
                    req["status"] = "blocked"
                else:
                    # Cedar over the whole proposal, with totals Valio gives for the summed order
                    quoted = self.orders.quote(proposals, date.fromisoformat(req["deliverBy"]), budget=budget)
                    decision = self.orders._decide(mandate, quoted)
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
                            actor=agent, budget=budget)
                        req["orderId"] = o["id"]
                        req["status"] = "waiting"
                        req["question"] = self._question(built, o)
                    else:
                        req["status"] = "blocked"
                        self._log(req, mandate, "validio", "decision", decision["sentence"], decision["ruleIds"], None)
            except (RequestError, CallBudgetExceeded, OrderError) as e:
                # refused before a decision: stored as blocked, with the reason in the ledger
                req["lines"], req["status"] = [], "blocked"
                req["decision"] = {"outcome": "block", "ruleIds": [],
                                   "sentence": f"Refused the request: {str(e).strip(chr(39))}. Nothing was ordered."}
                self._log(req, mandate, "validio", "decision", req["decision"]["sentence"], [], None)
            req["liveChecked"] = {"calls": budget.calls, "ids": budget.ids_sent, "idsPerCall": budget.per_call}
            self.store.put_request(req)
            self.store.idem_put(mandate.id, "request:" + idempotency_key, body_hash, req["id"])
            return self.get_request(req["id"])

    def _question(self, built: list[dict], order: dict) -> str:
        parts = [b["line"].get("swapSentence") for b in built if b["line"].get("swapSentence")]
        what = " and ".join(f"{ln['quantity']} {ln['unit']} of {ln['productId']} {ln['name']}" for ln in order["lines"])
        return " ".join(parts + [f"Order {what} for {order['totalCents'] / 100:.2f} EUR?"])

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
                                       idempotency_key=idempotency_key, request_id=request_id, actor=agent)
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
        if req.get("orderId"):
            o = self.orders.get(req["orderId"])
            req["status"] = {"placed": "ordered" if o.get("approvedBy") else "ordered_alone",
                             "waiting": "waiting", "rejected": "rejected", "blocked": "blocked"}[o["state"]]
            if o["state"] in ("placed", "blocked") or o.get("approvedBy"):
                req["decision"] = {**req.get("decision", {}), "sentence": self._latest_sentence(o)
                                   or req.get("decision", {}).get("sentence", "")}
            req["totalCents"] = o["totalCents"]
        return req

    def _latest_sentence(self, o: dict) -> str | None:
        entries = self.audit.list(order_id=o["id"])
        return entries[-1].sentence if entries else None

    def _log(self, req, mandate, actor, kind, sentence, rule_ids, order_id) -> None:
        self.audit.append(at=self.now(), actor=actor, kind=kind, sentence=sentence, facts=[],
                          mandate_id=mandate.id, disclosed=mandate.disclosed, rule_ids=rule_ids, order_id=order_id)


