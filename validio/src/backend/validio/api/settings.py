"""Rules and Settings for the web app (docs/ACCOUNTS-API.md, sections Rules and Settings).

GET  /api/rules                  what the agent may do, read from Spend Pass M-1 as last signed, the diet included
PUT  /api/rules                  money, substitutes and diet: one Save, one code, one new pass version, one entry
GET  /api/settings               kitchen, diet, login
PUT  /api/settings/kitchen       name and delivery address, no code; the customer number stays read only
PUT  /api/settings/diet          like Rules: the code, then M-1 signed again (kept for the first web app)
PUT  /api/settings/approval-code the account's own code, stored hashed in its row; not on a demo copy

Rules and Diet reach Cedar only through the pass, so both go through `resign`: the claims M-1 carries now,
the change on top, `seed.sign_again`, one ledger entry naming what changed. A Save that leaves out a field
keeps what the pass had, so Rules never reset the diet and the diet never resets the Rules.
"""

import base64
import json
import re
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Request, Response
from pydantic import Field, field_validator

from ..demo import seed
from ..matching.need import CLAIM_NAMES
from ..policy.mandate import NEVER_ALLERGENS, SUBSTITUTES_LISTED
from ..text.format import money
from . import codes
from .accounts import request_ctx
from .schemas import Model
from .state import Ctx

CtxDep = Annotated[Ctx, Depends(request_ctx)]
MAX_CENTS = 10_000_000  # 100,000.00 €
DIETS = Literal["FREE_FROM_LACTOSE", "FREE_FROM_GLUTEN", "VEGAN"]
# the Rules' diet in words: what every line must be, and the allergens it must never contain
MUST_BE = {"lactose-free": "FREE_FROM_LACTOSE", "gluten-free": "FREE_FROM_GLUTEN", "vegan": "VEGAN"}
NEVER = tuple(NEVER_ALLERGENS)
DEFAULT_NAME = "Hotel Espoo kitchen"
# the demo kitchen's saved Rules (the template, after the five scenes): O-1 and O-2 already used 1,190.10 € of
# the pass, so alone and approval count per order and only the week counts them all
DEMO_RULES = {"aloneUpToCents": 120000, "approvalUpToCents": 200000, "substitutes": "extra", "maxExtraPct": 5,
              "perWeekCents": 800000}


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
    d = date.fromisoformat(str(c["deliverBy"])) if c.get("deliverBy") else None
    split = c.get("split") or {}
    pct = float(split.get("maxExtraCostPct", 0))
    return [("Orders alone up to", money(c["autoLimitCents"])), ("Blocked above", money(c["hardCapCents"])),
            ("Diet", " and ".join(CLAIM_NAMES.get(x, x) for x in sorted(c.get("diet") or ())) or "none"),
            ("Delivered by", f"{d.day} {d:%b}" if d else "the day each request names"),
            ("Substitutes", "from Valio's list" if c.get("substitutes") == SUBSTITUTES_LISTED else "none alone"),
            ("Extra for a split", f"up to {pct:g} %" if pct else "none"),
            ("Per week", money(c["weekCapCents"]) if c.get("weekCapCents") is not None else "none"),
            ("Never contains", " and ".join(sorted(c.get("neverContains") or ())) or "nothing ruled out")]


def resign(ctx: Ctx, changes: dict, why: str) -> dict:
    """Sign M-1 again with `changes` on top of what it carries now: the next version, the old copy refused,
    one ledger entry by the owner. `why` names the version ("Rules changed", "Diet changed")."""
    with ctx.rt.lock:
        before = current_claims(ctx.db_path)
        if own_account(ctx):  # every signing starts a fresh window on the wall clock
            changes = {**changes, **seed.own_window(ctx.now())}
        seed.sign_again(ctx.db_path, ctx.keys_dir, {**before, **changes}, why=why, at=ctx.stamp())
        after = current_claims(ctx.db_path)
        changed = [f"{k} {a} → {b}." for (k, a), (_, b) in zip(_said(before), _said(after), strict=True) if a != b]
        pid = seed.SPEND_PASS_ID
        sentence = (f"Owner changed Spend Pass {pid}. " + " ".join(changed) if changed
                    else f"Owner signed Spend Pass {pid} again, nothing changed.")
        ctx.audit.append(at=ctx.stamp(), actor="owner", kind="spend_pass", sentence=sentence,
                         facts=[], mandate_id=pid, disclosed={}, rule_ids=[], order_id=None)
    return after


def own_account(ctx: Ctx) -> bool:
    """A kitchen's own account (not the local kitchen, not a demo copy): it runs on the wall clock."""
    return ctx.account is not None and not ctx.account["is_demo"]


def renew_window(ctx: Ctx) -> bool:
    """Sign M-1 again on the account's own window when it has none or it runs out soon. True when it signed."""
    with ctx.rt.lock:
        if seed.window_ok(ctx.db_path, ctx.now()):
            return False
        before = current_claims(ctx.db_path)
        seed.sign_again(ctx.db_path, ctx.keys_dir, {**before, **seed.own_window(ctx.now())},
                        why="Validity renewed", at=ctx.stamp())
        end = datetime.fromtimestamp(current_claims(ctx.db_path)["exp"], ctx.now().tzinfo)
        ctx.audit.append(at=ctx.stamp(), actor="validio", kind="spend_pass",
                         sentence=f"Validio signed Spend Pass {seed.SPEND_PASS_ID} again for 30 more days, "
                                  f"valid until {end:%d %b %Y}. Its limits did not change.",
                         facts=[], mandate_id=seed.SPEND_PASS_ID, disclosed={}, rule_ids=[], order_id=None)
    return True


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

class DietOptions(Model):
    must_be: list[str]
    never: list[str]


class DietRules(Model):
    must_be: list[str] = Field(description="every line must be all of these: " + ", ".join(MUST_BE))
    never: list[str] = Field(description="no line may contain any of these: " + ", ".join(NEVER))


class DietOut(DietRules):
    options: DietOptions


class RulesOut(Model):
    alone_up_to_cents: int
    approval_up_to_cents: int
    substitutes: Literal["off", "listed", "extra"]
    max_extra_pct: int
    per_week_cents: int | None
    saved: bool
    pass_version: int
    diet: DietOut


class RulesIn(Model):
    alone_up_to_cents: int = Field(ge=0, le=MAX_CENTS, description="the agent orders alone up to this")
    approval_up_to_cents: int = Field(ge=0, le=MAX_CENTS, description="needs approval up to this, blocked above")
    substitutes: Literal["off", "listed", "extra"] = Field(description="off, Valio's list, or Valio's list "
                                                           "with a split that may cost up to maxExtraPct more")
    max_extra_pct: int = Field(0, ge=0, le=20, description="only with substitutes 'extra'")
    per_week_cents: int | None = Field(None, ge=0, le=MAX_CENTS, description="all orders under the pass together; "
                                       "the two limits above always hold per order. null: no weekly limit")
    diet: DietRules | None = Field(None, description="left out: the diet stays as it is")
    code: str | None = Field(None, description="the 6 digit approval code, or the X-Approve-Code header")


def diet_out(c: dict) -> DietOut:
    words = {v: k for k, v in MUST_BE.items()}
    return DietOut(must_be=sorted(words.get(x, x) for x in c.get("diet") or ()),
                   never=sorted(c.get("neverContains") or ()),
                   options=DietOptions(must_be=list(MUST_BE), never=list(NEVER)))


def diet_claims(d: DietRules) -> dict:
    """The diet in words as the pass's claims; 422 for a word Validio does not know."""
    bad = [w for w in d.must_be if w not in MUST_BE] + [w for w in d.never if w not in NEVER_ALLERGENS]
    if bad:
        raise HTTPException(422, f"unknown diet word {', '.join(repr(w) for w in bad)}; mustBe takes "
                                 f"{', '.join(MUST_BE)}, never takes {', '.join(NEVER)}")
    return {"diet": sorted({MUST_BE[w] for w in d.must_be}), "neverContains": sorted(set(d.never))}


def _rules(ctx: Ctx) -> RulesOut:
    c = current_claims(ctx.db_path)
    split = c.get("split") or {}
    pct = round(float(split.get("maxExtraCostPct", 0)))
    subs = "off" if c.get("substitutes") != SUBSTITUTES_LISTED else "extra" if pct else "listed"
    return RulesOut(alone_up_to_cents=c["autoLimitCents"], approval_up_to_cents=c["hardCapCents"], substitutes=subs,
                    max_extra_pct=pct if subs == "extra" else 0, per_week_cents=c.get("weekCapCents"), saved=rules_saved(ctx.db_path),
                    pass_version=seed.pass_version(ctx.db_path, seed.SPEND_PASS_ID), diet=diet_out(c))


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
    if body.per_week_cents is not None and body.per_week_cents < body.approval_up_to_cents:
        raise HTTPException(422, f"per week {money(body.per_week_cents)} is below the approval limit "
                                 f"{money(body.approval_up_to_cents)}")
    diet = diet_claims(body.diet) if body.diet is not None else {}
    check_code(ctx, request, "rules", x_approve_code, body)
    pct = body.max_extra_pct if body.substitutes == "extra" else 0
    resign(ctx, {"autoLimitCents": body.alone_up_to_cents, "hardCapCents": body.approval_up_to_cents,
                 "substitutes": "never" if body.substitutes == "off" else SUBSTITUTES_LISTED,
                 "split": {"maxExtraCostPct": pct, "allowListedSubstitutes": body.substitutes != "off"},
                 "weekCapCents": body.per_week_cents, **diet},
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


class LoginChangeIn(Model):
    current_password: str = Field(max_length=200)
    email: str | None = Field(None, min_length=3, max_length=200, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str | None = Field(None, min_length=8, max_length=200)


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

    if ctx.account is not None and ctx.account["is_demo"]:
        raise HTTPException(403, "the demo kitchen keeps the demo code")
    check_code(ctx, request, "approval-code", None, ApproveIn(code=body.current))
    if not re.fullmatch(r"\d{6}", body.next):
        raise HTTPException(422, "next must be 6 digits")
    if ctx.account is not None:
        from .accounts import get_accounts, hash_secret

        get_accounts().update(ctx.account["id"], code_hash=hash_secret(body.next))
    else:
        codes.store(ctx.db_path, body.next)  # the local kitchen of make dev and the tests
    return Response(status_code=204)


@router.put("/settings/login", response_model=SettingsOut)
def put_login(ctx: CtxDep, body: LoginChangeIn):
    """A new email, a new password, or both, with the current password. Demo copies have no login."""
    from .accounts import get_accounts, hash_secret, secret_ok

    if ctx.account is None or ctx.account["is_demo"]:
        raise HTTPException(403, "this kitchen has no login to change")
    acc = get_accounts()
    row = acc.get(ctx.account["id"])
    if not secret_ok(body.current_password, row["pw_hash"]):
        raise HTTPException(403, "wrong password")
    fields: dict = {}
    if body.email:
        fields["email"] = body.email.strip().lower()
    if body.password:
        fields["pw_hash"] = hash_secret(body.password)
    if fields:
        try:
            acc.update(row["id"], **fields)
        except sqlite3.IntegrityError as e:
            raise HTTPException(409, "an account with this email exists") from e
        ctx.account.update(fields)  # the open account's row, cached with its store
    return _settings(ctx)
