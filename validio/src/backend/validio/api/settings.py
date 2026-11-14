"""Rules and Settings for the web app (docs/ACCOUNTS-API.md, sections Rules and Settings).

GET  /api/rules                  what the agent may do, read from Spend Pass M-1 as last signed
PUT  /api/rules                  one Save, one code, one new pass version, one ledger entry
GET  /api/settings               kitchen, diet, login
PUT  /api/settings/kitchen       name and delivery address, no code; the customer number stays read only
PUT  /api/settings/diet          like Rules: the code, then M-1 signed again
PUT  /api/settings/approval-code the account's own code, stored hashed

Rules and Diet reach Cedar only through the pass, so both go through `resign`: the claims M-1 carries now,
the change on top, `seed.sign_again`, one ledger entry naming what changed. A Save that leaves out a field
keeps what the pass had, so Rules never reset the diet and the diet never resets the Rules.
"""

import base64
import json
import re
import sqlite3
from datetime import date
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Request, Response
from pydantic import Field, field_validator

from ..demo import seed
from ..matching.need import CLAIM_NAMES
from ..policy.mandate import SUBSTITUTES_LISTED
from ..text.format import money
from . import codes
from .accounts import request_ctx
from .schemas import Model
from .state import Ctx

CtxDep = Annotated[Ctx, Depends(request_ctx)]
MAX_CENTS = 10_000_000  # 100,000.00 €
DIETS = Literal["FREE_FROM_LACTOSE", "FREE_FROM_GLUTEN", "VEGAN"]
DEFAULT_NAME = "Hotel Espoo kitchen"


def _kitchen_gate(request: Request, ctx: CtxDep) -> None:
    from .ui import kitchen

    kitchen(request, ctx)


router = APIRouter(prefix="/api", tags=["settings"], dependencies=[Depends(_kitchen_gate)])


# the pass as signed now

def current_claims(path: Path) -> dict:
    """Every claim of M-1 as the kitchen last signed it, disclosures opened. Our own store, so no check."""
    con = sqlite3.connect(path)
    try:
        (issuance,) = con.execute("select issuance from spend_pass where id = ?", (seed.SPEND_PASS_ID,)).fetchone()
    finally:
        con.close()

    def b64(s: str):
        return json.loads(base64.urlsafe_b64decode(s + "=" * (-len(s) % 4)))

    jwt, *disclosures = [p for p in issuance.split("~") if p]
    claims = b64(jwt.split(".")[1])
    for d in disclosures:
        _salt, name, value = b64(d)
        claims[name] = value
    return {k: v for k, v in claims.items() if k not in ("_sd", "_sd_alg", "cnf", "ver")}


def _said(c: dict) -> list[tuple[str, str]]:
    d = date.fromisoformat(str(c["deliverBy"]))
    split = c.get("split") or {}
    pct = float(split.get("maxExtraCostPct", 0))
    return [("Alone up to", money(c["autoLimitCents"])), ("Never above", money(c["hardCapCents"])),
            ("Diet", " and ".join(CLAIM_NAMES.get(x, x) for x in sorted(c.get("diet") or ())) or "none"),
            ("Delivered by", f"{d.day} {d:%b}"),
            ("Substitutes", "from Valio's list" if c.get("substitutes") == SUBSTITUTES_LISTED else "none alone"),
            ("Extra for a split", f"up to {pct:g} %" if pct else "none")]


def resign(ctx: Ctx, changes: dict, why: str) -> dict:
    """Sign M-1 again with `changes` on top of what it carries now: the next version, the old copy refused,
    one ledger entry by the owner. `why` names the version ("Rules changed", "Diet changed")."""
    with ctx.rt.lock:
        before = current_claims(ctx.db_path)
        seed.sign_again(ctx.db_path, ctx.keys_dir, {**before, **changes})
        after = current_claims(ctx.db_path)
        _note_version(ctx, why)
        changed = [f"{k} {a} → {b}." for (k, a), (_, b) in zip(_said(before), _said(after), strict=True) if a != b]
        pid = seed.SPEND_PASS_ID
        sentence = (f"Owner changed Spend Pass {pid}. " + " ".join(changed) if changed
                    else f"Owner signed Spend Pass {pid} again, nothing changed.")
        ctx.audit.append(at=ctx.now(), actor="owner", kind="spend_pass", sentence=sentence,
                         facts=[], mandate_id=pid, disclosed={}, rule_ids=[], order_id=None)
    return after


def _note_version(ctx: Ctx, why: str) -> None:
    """The version list of the Agent page, when the store keeps one (the connect step adds it)."""
    note = getattr(seed, "note_pass_version", None)
    if note is not None:
        note(ctx.db_path, seed.SPEND_PASS_ID, why)


# small values next to the pass, in the kitchen's own store

def _get(path: Path, key: str) -> str | None:
    con = sqlite3.connect(path)
    try:
        row = con.execute("select value from demo_state where key = ?", (key,)).fetchone()
    finally:
        con.close()
    return row[0] if row else None


def _put(path: Path, values: dict[str, str]) -> None:
    con = sqlite3.connect(path)
    try:
        con.executemany("insert or replace into demo_state values (?, ?)", list(values.items()))
        con.commit()
    finally:
        con.close()


def rules_saved(path: Path) -> bool:
    """False only for a kitchen whose Rules were never saved (a new account writes "0" when it is made)."""
    return _get(path, "rules_saved") != "0"


# Rules

class RulesOut(Model):
    alone_up_to_cents: int
    approval_up_to_cents: int
    substitutes: Literal["off", "listed", "extra"]
    max_extra_pct: int
    saved: bool
    pass_version: int


class RulesIn(Model):
    alone_up_to_cents: int = Field(ge=0, le=MAX_CENTS, description="the agent orders alone up to this")
    approval_up_to_cents: int = Field(ge=0, le=MAX_CENTS, description="needs approval up to this, blocked above")
    substitutes: Literal["off", "listed", "extra"] = Field(description="off, Valio's list, or Valio's list "
                                                           "with a split that may cost up to maxExtraPct more")
    max_extra_pct: int = Field(0, ge=0, le=20, description="only with substitutes 'extra'")
    code: str | None = Field(None, description="the 6 digit approval code, or the X-Approve-Code header")


def _rules(ctx: Ctx) -> RulesOut:
    c = current_claims(ctx.db_path)
    split = c.get("split") or {}
    pct = round(float(split.get("maxExtraCostPct", 0)))
    subs = "off" if c.get("substitutes") != SUBSTITUTES_LISTED else "extra" if pct else "listed"
    return RulesOut(alone_up_to_cents=c["autoLimitCents"], approval_up_to_cents=c["hardCapCents"], substitutes=subs,
                    max_extra_pct=pct if subs == "extra" else 0, saved=rules_saved(ctx.db_path),
                    pass_version=seed.pass_version(ctx.db_path, seed.SPEND_PASS_ID))


@router.get("/rules", response_model=RulesOut)
def get_rules(ctx: CtxDep):
    return _rules(ctx)


@router.put("/rules", response_model=RulesOut)
def put_rules(ctx: CtxDep, request: Request, body: RulesIn,
              x_approve_code: Annotated[str | None, Header()] = None):
    from .ui import check_code

    if body.alone_up_to_cents > body.approval_up_to_cents:
        raise HTTPException(422, f"alone up to {money(body.alone_up_to_cents)} is above the approval limit "
                                 f"{money(body.approval_up_to_cents)}")
    check_code(ctx, request, "rules", x_approve_code, body)
    pct = body.max_extra_pct if body.substitutes == "extra" else 0
    resign(ctx, {"autoLimitCents": body.alone_up_to_cents, "hardCapCents": body.approval_up_to_cents,
                 "substitutes": "never" if body.substitutes == "off" else SUBSTITUTES_LISTED,
                 "split": {"maxExtraCostPct": pct, "allowListedSubstitutes": body.substitutes != "off"}},
           "Rules changed")
    _put(ctx.db_path, {"rules_saved": "1"})
    return _rules(ctx)


# Settings

class KitchenOut(Model):
    name: str
    customer_number: str
    delivery_address: str


class LoginOut(Model):
    email: str | None = None


class SettingsOut(Model):
    kitchen: KitchenOut
    diet: list[str]
    login: LoginOut


class KitchenIn(Model):
    name: str = Field(description="the kitchen's name, 1 to 80 characters")
    delivery_address: str = Field("", max_length=200)

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = " ".join(v.split())
        if not 1 <= len(v) <= 80:
            raise ValueError("name must be 1 to 80 characters")
        return v


class DietIn(Model):
    diet: list[DIETS] = Field(description="every line must keep these")
    code: str | None = Field(None, description="the 6 digit approval code, or the X-Approve-Code header")


class ApprovalCodeIn(Model):
    current: str
    next: str = Field(description="the new 6 digit code")


def _settings(ctx: Ctx) -> SettingsOut:
    path = ctx.db_path
    return SettingsOut(
        kitchen=KitchenOut(name=_get(path, "kitchen_name") or DEFAULT_NAME,
                           customer_number=ctx.account["customer"] if ctx.account else ctx.settings.valio_customer,
                           delivery_address=_get(path, "delivery_address") or ""),
        diet=sorted(current_claims(path).get("diet") or []),
        login=LoginOut(email=ctx.account["email"] if ctx.account else None))


@router.get("/settings", response_model=SettingsOut)
def get_settings(ctx: CtxDep):
    return _settings(ctx)


@router.put("/settings/kitchen", response_model=SettingsOut)
def put_kitchen(ctx: CtxDep, body: KitchenIn):
    _put(ctx.db_path, {"kitchen_name": body.name, "delivery_address": " ".join(body.delivery_address.split())})
    return _settings(ctx)


@router.put("/settings/diet", response_model=SettingsOut)
def put_diet(ctx: CtxDep, request: Request, body: DietIn, x_approve_code: Annotated[str | None, Header()] = None):
    from .ui import check_code

    check_code(ctx, request, "diet", x_approve_code, body)
    resign(ctx, {"diet": sorted(set(body.diet))}, "Diet changed")
    return _settings(ctx)


@router.put("/settings/approval-code", status_code=204)
def put_approval_code(ctx: CtxDep, request: Request, body: Annotated[ApprovalCodeIn, Body()]):
    from .schemas import ApproveIn
    from .ui import check_code

    check_code(ctx, request, "approval-code", None, ApproveIn(code=body.current))
    if not re.fullmatch(r"\d{6}", body.next):
        raise HTTPException(422, "next must be 6 digits")
    codes.store(ctx.db_path, body.next)
    return Response(status_code=204)
