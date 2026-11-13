"""Order service: every number comes from Valio again, never from the agent.

submit   re-quotes price and availability, asks the Hard Lines and lands in placed, waiting or blocked.
         The idempotency key makes a retry return the same order.
approve  only from waiting. Asks Valio again and refuses if a price rose more than 2 %, a line can no
         longer be delivered, the cut-off or the deadline has passed or the Spend Pass is no longer valid.
         Only then is the order placed.

Every state change and its ledger entry are one SQLite transaction (the ledger shares the store's
connection), under one lock that the demo reset takes too.
"""

import hashlib
import json
import re
import threading
from collections.abc import Callable
from dataclasses import asdict, dataclass, fields
from datetime import date, datetime
from pathlib import Path
from typing import Any

from ..audit.log import NEVER_LOGGED, AuditLog
from ..audit.sentences import eur, ordered_alone
from ..catalog.store import Catalog
from ..policy.decide import Outcome, context_for, decide
from ..policy.mandate import Mandate, effective_deadline
from ..text.format import and_list, count, display_name, qty_text
from ..trust.levels import PLACEHOLDER_NOTE, Fact, price_fact, quantity_fact, stock_in_sales_units
from ..valio.budget import CallBudget
from ..valio.models import Availability
from .store import NotFound, Store

MAX_PRICE_RISE_BP = 200  # 2 %
OUTCOME = {Outcome.ALLOW: "auto_order", Outcome.ESCALATE: "ask_human", Outcome.DENY: "block"}
SEVERITY = {"auto_order": 0, "ask_human": 1, "block": 2}
STATE = {"auto_order": "placed", "ask_human": "waiting", "block": "blocked"}


class OrderError(Exception):
    pass


class OrderStateError(OrderError):
    """The order is not in a state that allows this (HTTP 409)."""


class IdempotencyConflict(OrderError):
    """The same idempotency key came with another body (HTTP 409)."""


def revoke_pass(store: Store, audit: AuditLog, pass_id: str, at: datetime, actor: str = "kitchen") -> bool:
    """The kitchen stops a Spend Pass early: from now on every presentation of it and every approve of an order
    it holds is refused. One ledger entry. False when the pass was revoked already."""
    if not store.revoke(pass_id, at.isoformat(), actor):
        return False
    audit.append(at=at, actor=actor, kind="revocation",
                 sentence=f"The kitchen revoked Spend Pass {pass_id}. Validio refuses it from now on, also to "
                          "approve its waiting orders.",
                 facts=[], mandate_id=pass_id, disclosed={}, rule_ids=[], order_id=None)
    return True


class ApproveRefused(OrderError):
    """Valio's answer changed since the question was asked (HTTP 409). The order keeps waiting."""


class ServiceClosed(Exception):
    """The demo was reset while this call waited; its store is gone (HTTP 503, send it again)."""


def day(d: date | str) -> str:
    d = date.fromisoformat(d) if isinstance(d, str) else d
    return f"{d.day} {d.strftime('%b')}"


@dataclass(frozen=True)
class LineIn:
    product_id: str
    sales_qty: int
    is_substitute: bool = False
    on_valio_list: bool = False
    proposed_price_cents: int | None = None  # what the agent says it costs. Never read.


def fact_dict(f: Fact) -> dict[str, Any]:
    d = {"field": f.field, "value": f.value, "grade": str(f.level), "source": f.source, "note": f.note}
    if str(f.level) == "attested_until" and f.note.startswith("until "):
        d["until"] = f.note.removeprefix("until ")
    return d


def mandate_dict(m: Mandate) -> dict[str, Any]:
    d = asdict(m)
    d["disclosed"] = {k: v for k, v in m.disclosed.items() if k not in NEVER_LOGGED}
    return d


def mandate_from(d: dict[str, Any]) -> Mandate:
    d = dict(d)
    for k in ("categories", "diet", "prefer_labels"):
        if d.get(k) is not None:
            d[k] = tuple(d[k])
    return Mandate(**{f.name: d.get(f.name) for f in fields(Mandate)})


def _hash(body: Any) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _short(p, stock: float, needed: int) -> str:
    if stock <= 0:
        return f"{display_name(p.name_en)} is out of stock at Valio, {qty_text(needed, p.sales_unit)} needed"
    return f"Only {qty_text(stock, p.sales_unit)} of {display_name(p.name_en)} in stock, {count(needed)} needed"


def _names(quoted: list[dict], ids: list[str]) -> list[str]:
    return [display_name(ln["name"]) for ln in quoted if ln["productId"] in ids]


def _with_stock(a: Availability | None, amount: float) -> Availability | None:
    from dataclasses import replace

    return None if a is None else replace(a, lines=[replace(ln, amount=float(amount)) for ln in a.lines])


class OrderService:
    def __init__(self, store: Store, catalog: Catalog, valio, audit: AuditLog,
                 clock: Callable[[], datetime], adjust: Callable[[dict], dict] | None = None,
                 max_ids: int = 40, lock: "threading.RLock | None" = None):
        self.store, self.catalog, self.valio, self.audit = store, catalog, valio, audit
        if audit.path.resolve() == Path(store.path).resolve():
            audit.join(store.con, store.lock)  # one connection, else the ledger waits on the store's own write lock
        self.clock = clock
        self.adjust = adjust or (lambda avail: avail)  # the demo stock-out switch
        self.max_ids = max_ids
        self.lock = lock or threading.RLock()
        self.closed = False

    def check_open(self) -> None:
        """Call with the lock held: a reset may have replaced this service while the call waited."""
        if self.closed:
            raise ServiceClosed("the demo was reset while this call waited, send it again")

    # Valio, asked again

    def quote(self, lines: list[LineIn], deliver_by: date, stock_override: dict[str, float] | None = None,
              budget: CallBudget | None = None) -> list[dict[str, Any]]:
        budget = budget or CallBudget(self.max_ids)
        ids = [ln.product_id for ln in lines]
        quotes = self.valio.price(ids, deliver_by, budget)
        avail = self.adjust(self.valio.availability(ids, deliver_by, budget))
        out = []
        for ln in lines:
            p = self.catalog.get(ln.product_id)
            if p is None:
                raise OrderError(f"unknown product {ln.product_id}")
            q, a = quotes.get(p.id), avail.get(p.id)
            if stock_override and p.id in stock_override:
                a = _with_stock(a, stock_override[p.id])
            price = None if q is None or q.error else q.price_cents
            qf = quantity_fact(a, p)
            stock = stock_in_sales_units(p, a)  # in the product's sales unit, None when not a real count
            short = stock is not None and stock < ln.sales_qty
            out.append({
                "productId": p.id, "name": p.name_en, "quantity": int(ln.sales_qty), "unit": p.sales_unit,
                "priceCents": price, "totalCents": None if price is None else price * int(ln.sales_qty),
                "priceValidTo": q.valid_to.isoformat() if q and q.valid_to else None,
                "deliveryDate": a.lines[0].available.isoformat() if a and a.lines else None,
                "deliverable": bool(a and a.deliverable) and not short,
                "short": _short(p, stock, ln.sales_qty) if short else None,
                "isSubstitute": ln.is_substitute, "onValioList": ln.on_valio_list,
                "facts": [fact_dict(qf), fact_dict(price_fact(q))],
                "_product": p, "_avail": a,
            })
        return out

    def _decide(self, mandate: Mandate, quoted: list[dict], required_claims: list[str] | None = None,
                split_base_cents: int | None = None, deliver_by: date | None = None) -> dict[str, Any]:
        return self._judge(mandate, quoted, required_claims, split_base_cents, deliver_by)[0]

    def _judge(self, mandate: Mandate, quoted: list[dict], required_claims: list[str] | None = None,
               split_base_cents: int | None = None, deliver_by: date | None = None) -> tuple[dict, list]:
        """The decision for the whole order and, per line, (outcome, Cedar decision, line, context)."""
        missing = [ln["productId"] for ln in quoted if ln["priceCents"] is None]
        if missing:
            return {"outcome": "block", "ruleIds": [],
                    "sentence": f"Blocked: Valio has no price for {and_list(_names(quoted, missing))}."}, []
        total = sum(ln["totalCents"] for ln in quoted)
        per = []
        for ln in quoted:
            ctx = context_for(mandate, ln["_product"], ln["_avail"], total_cents=total, now=self.clock(),
                              is_substitute=ln["isSubstitute"], on_valio_list=ln["onValioList"],
                              split_base_cents=split_base_cents, required_claims=required_claims,
                              sales_qty=ln["quantity"], deliver_by=deliver_by)
            per.append((OUTCOME[(d := decide(ctx, product_id=ln["productId"])).outcome], d, ln, ctx))
        worst = max((o for o, *_ in per), key=SEVERITY.__getitem__)
        rule_ids: list[str] = []
        sentences: list[str] = []
        for o, d, ln, _c in per:
            if o != worst:
                continue
            rule_ids += [r for r in d.rule_ids if r not in rule_ids]
            if ln["short"]:
                sentences.append(ln["short"] + ".")
            if ln["isSubstitute"] and not ln["onValioList"] and worst == "ask_human" \
                    and "not on Valio's list" not in d.sentence:
                sentences.append(f"{display_name(ln['name'])} is a substitute that is not on Valio's list.")
            if d.sentence not in sentences:
                sentences.append(d.sentence)
        return {"outcome": worst, "ruleIds": rule_ids, "sentence": " ".join(sentences)}, per

    @staticmethod
    def _public(lines: list[dict]) -> list[dict]:
        return [{k: v for k, v in ln.items() if not k.startswith("_")} for ln in lines]

    # The order lifecycle

    def submit(self, *, mandate: Mandate, lines: list[LineIn], deliver_by: date, idempotency_key: str,
               request_id: str | None = None, actor: str | None = None,
               stock_override: dict[str, float] | None = None, budget: CallBudget | None = None,
               required_claims: tuple[str, ...] | list[str] | None = None,
               split_base_cents: int | None = None) -> dict:
        """`required_claims` is the line's own diet (a Steady Order line), None means the Spend Pass diet.
        `split_base_cents` marks the order as a split and is what the wanted amount alone would cost."""
        if not lines:
            raise OrderError("an order needs at least one line")
        body_hash = _hash({"lines": [(ln.product_id, ln.sales_qty, ln.is_substitute, ln.on_valio_list)
                                     for ln in lines], "deliverBy": deliver_by.isoformat(),
                           "requestId": request_id, "requiredClaims": required_claims,
                           "splitBaseCents": split_base_cents})
        with self.lock, self.store.tx():
            self.check_open()
            seen = self.store.idem_get(mandate.id, idempotency_key)
            if seen:
                if seen[0] != body_hash:
                    raise IdempotencyConflict("this idempotency key was used for another order")
                return self.get(seen[1])
            quoted = self.quote(lines, deliver_by, stock_override, budget)
            claims = None if required_claims is None else list(required_claims)
            decision = self._decide(mandate, quoted, claims, split_base_cents, deliver_by)
            state = STATE[decision["outcome"]]
            total = sum(ln["totalCents"] or 0 for ln in quoted)
            now = self.clock().isoformat()
            order = self.store.new_order({
                "requestId": request_id, "state": state, "lines": self._public(quoted), "totalCents": total,
                "deliverBy": deliver_by.isoformat(), "decision": decision, "history": [{"state": state, "at": now}],
                "spendPassId": mandate.id, "mandate": mandate_dict(mandate), "agent": actor or mandate.holder,
                "requiredClaims": claims, "splitBaseCents": split_base_cents,
            })
            self.store.idem_put(mandate.id, idempotency_key, body_hash, order["id"])
            if state == "placed":
                self._log(order, actor or mandate.holder, "order", self._placed_sentence(order, None),
                          decision["ruleIds"])
            else:
                self._log(order, "validio", "decision", decision["sentence"], decision["ruleIds"])
            return order

    def get(self, order_id: str) -> dict:
        o = self.store.order(order_id)
        if o is None:
            raise NotFound(f"no order {order_id}")
        return o

    def _time_problems(self, mandate: Mandate, deliver_by: date) -> list[str]:
        now = self.clock()
        if now.timestamp() >= mandate.expires:
            end = datetime.fromtimestamp(mandate.expires, now.tzinfo)
            return [f"Spend Pass {mandate.id} expired at {end:%d %b %H:%M}"]
        if now.timestamp() < mandate.not_before:
            return [f"Spend Pass {mandate.id} is not valid yet"]
        deadline = effective_deadline(mandate, deliver_by)
        if deadline is None or now.date() > deadline:
            return [f"the delivery date {day(deliver_by)} has passed"]
        return []

    def approve(self, order_id: str, approver: str) -> dict:
        with self.lock:
            self.check_open()
            o = self.get(order_id)
            if o["state"] != "waiting":
                raise OrderStateError(f"order {order_id} is {o['state']}, only a waiting order can be approved")
            mandate = mandate_from(o["mandate"])
            if self.store.is_revoked(mandate.id):
                sentence = f"Approval refused: Spend Pass {mandate.id} was revoked by the kitchen."
                self._log(o, "validio", "decision", sentence, [])
                raise ApproveRefused(sentence)
            deliver_by = date.fromisoformat(o["deliverBy"])
            problems = self._time_problems(mandate, deliver_by)
            if problems:
                self._refuse(o, problems)
            lines = [LineIn(ln["productId"], ln["quantity"], ln["isSubstitute"], ln["onValioList"])
                     for ln in o["lines"]]
            fresh = self.quote(lines, deliver_by)
            for old, new in zip(o["lines"], fresh, strict=True):
                if not new["deliverable"]:
                    problems.append(new["short"] or f"{display_name(new['name'])} can no longer be delivered")
                elif new["priceCents"] is None:
                    problems.append(f"Valio has no price for {display_name(new['name'])} any more")
                elif old["priceCents"] and new["priceCents"] * 10000 > old["priceCents"] * (10000 + MAX_PRICE_RISE_BP):
                    problems.append(f"the price of {display_name(new['name'])} rose from {eur(old['priceCents'])} "
                                    f"to {eur(new['priceCents'])}, more than 2 %")
            if not problems:
                # a person may lift "ask", never a block, a passed cut-off or a late delivery
                again, per = self._judge(mandate, fresh, o.get("requiredClaims"), o.get("splitBaseCents"),
                                         deliver_by)
                if again["outcome"] == "block":
                    problems.append(again["sentence"])
                for _o, _d, ln, c in per:
                    a = ln["_avail"]
                    if not c.cutoff_ok:
                        when = f" ({a.closing_time:%d %b %H:%M})" if a is not None and a.closing_time else ""
                        problems.append(f"the order cut-off for {display_name(ln['name'])} has passed{when}")
                    elif not c.delivery_in_time:
                        problems.append((f"Valio now delivers {display_name(ln['name'])} on {day(ln['deliveryDate'])}, "
                                         f"after {day(deliver_by)}") if ln["deliveryDate"] else
                                        f"Valio gives no delivery date for {display_name(ln['name'])}")
            if problems:
                self._refuse(o, problems)
            now = self.clock().isoformat()
            o["lines"] = self._public(fresh)
            o["totalCents"] = sum(ln["totalCents"] for ln in fresh)
            o["history"] += [{"state": "approved", "at": now}, {"state": "placed", "at": now}]
            o["state"] = "placed"
            o["approvedBy"] = approver
            with self.store.tx():
                self.store.put_order(o)
                self._log(o, approver, "approval", f"{approver.split(':')[-1].capitalize()} approved "
                          f"{self._parts(o)} for {eur(o['totalCents'])}.", [])
                self._log(o, "validio", "order", self._placed_sentence(o, approver), o["decision"]["ruleIds"])
            return o

    def _refuse(self, o: dict, problems: list[str]) -> None:
        sentence = "Approval refused, Valio was asked again: " + and_list(problems) + "."
        self._log(o, "validio", "decision", sentence, [])
        raise ApproveRefused(sentence)

    def reject(self, order_id: str, approver: str, reason: str | None = None) -> dict:
        with self.lock, self.store.tx():
            self.check_open()
            o = self.get(order_id)
            if o["state"] != "waiting":
                raise OrderStateError(f"order {order_id} is {o['state']}, only a waiting order can be rejected")
            o["state"] = "rejected"
            o["history"].append({"state": "rejected", "at": self.clock().isoformat()})
            self.store.put_order(o)
            why = f" ({reason})" if reason else ""
            self._log(o, approver, "approval",
                      f"{approver.split(':')[-1].capitalize()} rejected {self._parts(o)}{why}. Nothing was ordered.",
                      [])
            return o

    # Sentences and ledger

    @staticmethod
    def _parts(o: dict, ids: bool = True) -> str:
        """The lines in words. The ledger keeps the product ids next to the names, the question does not."""
        return and_list([f"{qty_text(ln['quantity'], ln['unit'])} of {display_name(ln['name'])}"
                         + (f" ({ln['productId']})" if ids else "") for ln in o["lines"]])

    def _placed_sentence(self, o: dict, approver: str | None) -> str:
        m = o["mandate"]
        ln = o["lines"][0]
        if approver is None and len(o["lines"]) == 1 and ln["priceValidTo"] and m.get("auto_limit_cents"):
            return ordered_alone(quantity=ln["quantity"], unit=ln["unit"], product_id=ln["productId"],
                                 product_name=ln["name"], total_cents=o["totalCents"],
                                 price_valid_until=ln["priceValidTo"], delivery_date=ln["deliveryDate"],
                                 mandate_id=m["id"], auto_limit_cents=m["auto_limit_cents"])
        names = self._parts(o)
        if approver is None:
            return f"Ordered {names} for {eur(o['totalCents'])} without a person. Inside Spend Pass {m['id']}."
        role = approver.split(":")[-1]  # the role only, never the approver list of the Spend Pass
        return (f"Placed order {o['id']}: {names} for {eur(o['totalCents'])} after the {role} approved. "
                f"Valio was asked again: every line is delivered by {day(o['deliverBy'])}, before its order "
                f"cut-off, inside Spend Pass {m['id']}, and no price rose more than 2 %.")

    def _log(self, o: dict, actor: str, kind: str, sentence: str, rule_ids: list[str]) -> None:
        m = o["mandate"]
        facts = [f for ln in o["lines"] for f in ln["facts"]]
        if kind == "order":  # say so when the quantity rests on a placeholder, not a real count
            for ln in o["lines"]:
                for f in ln["facts"]:
                    hit = re.match(r"Valio reports (\d+), (" + PLACEHOLDER_NOTE + r"; treated as in stock)",
                                  f.get("note") or "")
                    if f["field"] == "quantity" and hit:
                        what = "the stock" if len(o["lines"]) == 1 else f"the stock of {display_name(ln['name'])}"
                        sentence += f" Valio gives no real count of {what}, so Validio treats it as in stock."
        self.audit.append(at=self.clock(), actor=actor, kind=kind, sentence=sentence, facts=facts,
                          mandate_id=m["id"], disclosed=m["disclosed"], rule_ids=rule_ids, order_id=o["id"])
