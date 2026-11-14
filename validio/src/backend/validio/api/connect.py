"""Connect an agent to the kitchen (docs/ACCOUNTS-API.md, "Agent").

The web app asks for a pairing code, the agent sends it with its name and public key, the person sees the
consent screen and allows: the kitchen signs Spend Pass M-1 again, bound to that key, as the next version.
Pause is a flag checked when a pass is verified; a refused call writes one ledger entry. Disconnect signs
M-1 again to a key nobody holds, so the agent's copy is superseded; it never revokes, because a revoked id
cannot come back on the next connect.

Everything lives in the kitchen's own database, so each account has its own agent. A store that never saw
this table has the demo agent connected: the seed signs M-1 to the demo agent's key."""

import hashlib
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from jwcrypto.jwk import JWK
from pydantic import Field

from ..demo import seed
from ..policy.mandate import DEMO_CLAIMS, SUBSTITUTES_LISTED, Mandate, MandateError, load_or_create_key
from ..text.format import money
from .schemas import Model
from .state import Ctx

ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"  # no 0, O, 1, I, L
CODE_TTL = timedelta(minutes=10)
MAX_PAIR_TRIES = 5
DEMO_AGENT = "Demo agent"
MCP_NAME = "MCP agent"  # the name on the consent screen and in the ledger for an MCP agent Validio signs for
PAUSED = "the kitchen paused this agent"
NOT_CONNECTED = "no agent is connected to this kitchen"

SCHEMA = """create table if not exists agent_link (
  id integer primary key check (id = 1), state text not null, name text, sub text, jwk text, key_id text,
  connected_at text, last_used_at text, pending_name text, pending_jwk text,
  code text, code_expires text, code_status text, wrong_tries integer not null default 0, verify_code text)"""
COLUMNS = ("state", "name", "sub", "jwk", "key_id", "connected_at", "last_used_at", "pending_name", "pending_jwk",
           "code", "code_expires", "code_status", "wrong_tries", "verify_code")


# shapes


class Pairing(Model):
    code: str
    expires_at: str
    mcp_url: str
    api_url: str


class Consent(Model):
    name: str
    key_id: str
    may: list[str]
    verify_code: str = Field(description="XXX-XXX, new for this connection; the agent shows the same code")


class AgentInfo(Model):
    name: str
    kind: Literal["agent", "mcp"] = "agent"
    key_id: str
    connected_at: str
    last_used_at: str | None
    pass_id: str
    pass_version: int


class PassVersion(Model):
    version: int
    at: str | None
    why: str


class AgentState(Model):
    state: Literal["none", "pairing", "consent", "active", "paused"]
    pairing: Pairing | None = None
    consent: Consent | None = None
    agent: AgentInfo | None = None
    versions: list[PassVersion]


class PauseIn(Model):
    paused: bool


class PairIn(Model):
    code: str = Field(min_length=8, max_length=12)
    name: str = Field(min_length=1, max_length=60)
    public_jwk: dict = Field(description="the agent's public P-256 key as a JWK")


class PairOut(Model):
    status: Literal["consent"]
    verify_code: str = Field(description="XXX-XXX: show it to the user, it must match the code on the kitchen's "
                                         "Agent page before the kitchen presses Allow")


class PassOut(Model):
    status: Literal["consent", "allowed", "denied"]
    spend_pass: str | None = Field(None, description="the issued Spend Pass, bound to the agent's key")


# storage


@dataclass
class Link:
    state: str
    name: str | None = None
    sub: str | None = None
    jwk: str | None = None
    key_id: str | None = None
    connected_at: str | None = None
    last_used_at: str | None = None
    pending_name: str | None = None
    pending_jwk: str | None = None
    code: str | None = None
    code_expires: str | None = None
    code_status: str | None = None
    wrong_tries: int = 0
    verify_code: str | None = None


def _wall() -> datetime:
    """Codes expire on the real clock; the demo clock stands still."""
    return datetime.now(UTC)


def _norm(code: str) -> str:
    """Sent with or without the dash, any case."""
    return "".join(code.upper().split()).replace("-", "")


def demo_key(ctx: Ctx) -> JWK:
    return load_or_create_key(ctx.keys_dir / "agent-es256.json")


def key_id(jwk: JWK) -> str:
    return jwk.thumbprint()[:8]


def verify_code() -> str:
    """A fresh verification code for one connection, XXX-XXX without look-alikes."""
    c = "".join(secrets.choice(ALPHABET) for _ in range(6))
    return f"{c[:3]}-{c[3:]}"


def _con(ctx_or_path) -> sqlite3.Connection:
    con = sqlite3.connect(getattr(ctx_or_path, "db_path", ctx_or_path), timeout=10)
    con.execute(SCHEMA)
    if "verify_code" not in {r[1] for r in con.execute("pragma table_info(agent_link)")}:
        con.execute("alter table agent_link add column verify_code text")  # a store from before the code
    return con


def load(ctx: Ctx) -> Link:
    con = _con(ctx)
    try:
        row = con.execute(f"select {', '.join(COLUMNS)} from agent_link where id = 1").fetchone()
    finally:
        con.close()
    if row:
        return Link(*row)
    pub = demo_key(ctx)
    return Link("active", DEMO_AGENT, DEMO_CLAIMS["sub"], pub.export_public(), key_id(pub), seed.NOW.isoformat())


def save(ctx: Ctx | Path, link: Link) -> None:
    con = _con(ctx)
    try:
        con.execute(f"insert or replace into agent_link (id, {', '.join(COLUMNS)}) values (1, {', '.join('?' * len(COLUMNS))})",
                    tuple(getattr(link, c) for c in COLUMNS))
        con.commit()
    finally:
        con.close()


def leave_unconnected(db_path: Path) -> None:
    """A kitchen that starts without an agent (the demo template after its scenes, a new account): no ledger
    entry, no new version. Until the person connects one, every pass is refused at verify."""
    save(Path(db_path), Link("none"))


def _entry(ctx: Ctx, sentence: str, actor: str = "owner") -> None:
    ctx.audit.append(at=ctx.now(), actor=actor, kind="agent", sentence=sentence, facts=[],
                     mandate_id=seed.SPEND_PASS_ID, disclosed={}, rule_ids=[], order_id=None)


# what the web app sees


def account_id(ctx: Ctx) -> str | None:
    """The account behind this ctx; None for the local kitchen."""
    return ctx.account["id"] if ctx.account else None


def base_url(request: Request | None) -> str:
    """Absolute on a request (https unless on this machine), else empty."""
    if request is None:
        return ""
    local = request.url.hostname in ("127.0.0.1", "localhost", "::1", "testserver")
    return f"{'http' if local else 'https'}://{request.url.netloc}"


def urls(ctx: Ctx, request: Request | None) -> tuple[str, str]:
    """Absolute on a request (https unless on this machine), else from the root."""
    base = base_url(request)
    acct = account_id(ctx)
    k = f"/k/{acct}" if acct else ""
    return f"{base}/mcp{k}/", f"{base}/agent/v1{k}"


def may(ctx: Ctx) -> list[str]:
    """The pass's limits in words for the consent screen, said as the Rules say them."""
    from .settings import current_claims, rules_saved  # settings reaches the agent link through the pass

    if not rules_saved(ctx.db_path):
        return ["Every order needs approval"]
    c = current_claims(ctx.db_path)
    out = [f"Orders alone up to {money(c['autoLimitCents'])}", f"Needs approval up to {money(c['hardCapCents'])}",
           f"Blocked above {money(c['hardCapCents'])}"]
    if c.get("weekCapCents") is not None:
        out.append(f"Per week up to {money(c['weekCapCents'])}")
    pct = round(float((c.get("split") or {}).get("maxExtraCostPct", 0)))
    if c.get("substitutes") != SUBSTITUTES_LISTED:
        out.append("No substitutes")
    else:
        out.append(f"Substitutes up to {pct} % extra" if pct else "Substitutes from Valio's list")
    return out


def last_used(ctx: Ctx, link: Link) -> str | None:
    """The agent's last entry in the ledger (what it asked for, under its own name), so the Agent page and the
    ledger tell the same time; the last verified call when the ledger has none of it yet."""
    mine = [e.at for e in ctx.audit.list() if link.sub and e.actor == link.sub]
    return max(mine, key=datetime.fromisoformat) if mine else link.last_used_at


def view(ctx: Ctx, request: Request | None = None, link: Link | None = None) -> AgentState:
    link = link or load(ctx)
    versions = [PassVersion(**v) for v in seed.pass_versions(ctx.db_path)]
    out = AgentState(state=link.state, versions=versions)
    if link.state == "pairing":
        mcp, api = urls(ctx, request)
        held = _connector(ctx)
        if not (held and held[2]):  # a pairing started before connector URLs existed gets one now
            with ctx.rt.lock:
                held = _connector(ctx)
                if not (held and held[2]):
                    token = secrets.token_urlsafe(32)
                    _set_connector(ctx, JWK.generate(kty="EC", crv="P-256").export_private(), _token_hash(token), token)
                    held = _connector(ctx)
        if held and held[2]:  # any MCP agent: the connector URL; signing agents use the code and /mcp/k/
            mcp = f"{base_url(request)}/mcp/c/{held[2]}/"
        code = link.code
        out.pairing = Pairing(code=f"{code[:4]}-{code[4:]}", expires_at=link.code_expires, mcp_url=mcp, api_url=api)
    if link.state == "consent":
        out.consent = Consent(name=link.pending_name, key_id=key_id(JWK.from_json(link.pending_jwk)), may=may(ctx),
                              verify_code=consent_code(ctx))
    if link.state in ("active", "paused"):
        out.agent = AgentInfo(name=link.name, key_id=link.key_id, connected_at=link.connected_at,
                              kind="mcp" if connector_key(ctx, link) else "agent",
                              last_used_at=last_used(ctx, link), pass_id=seed.SPEND_PASS_ID,
                              pass_version=seed.pass_version(ctx.db_path, seed.SPEND_PASS_ID))
    return out


# the steps


def pair(ctx: Ctx) -> Link:
    with ctx.rt.lock:
        link = load(ctx)
        if link.state in ("active", "paused"):
            raise HTTPException(409, "disconnect the agent first")
        drop_connector(ctx)
        # any MCP agent can take the connector URL instead of the code: Validio holds its key
        token = secrets.token_urlsafe(32)
        _set_connector(ctx, JWK.generate(kty="EC", crv="P-256").export_private(), _token_hash(token), token)
        code = "".join(secrets.choice(ALPHABET) for _ in range(8))
        link = Link("pairing", code=code, code_expires=(_wall() + CODE_TTL).isoformat(),
                    code_status="pairing")
        save(ctx, link)
    return link


def _public(jwk: dict) -> JWK:
    if "d" in jwk:
        raise HTTPException(422, "publicJwk holds a private key, send only the public part")
    try:
        key = JWK(**jwk)
    except Exception as e:
        raise HTTPException(422, "publicJwk is not a JWK") from e
    if jwk.get("kty") != "EC" or jwk.get("crv") != "P-256":
        raise HTTPException(422, "publicJwk must be a P-256 key")
    return key


def agent_pair(ctx: Ctx, body: PairIn) -> str:
    """The agent answers the code with its name and key. 404 for a wrong or expired code; five wrong codes
    end the pairing. Returns the verification code the consent screen shows."""
    key = _public(body.public_jwk)
    name = " ".join(body.name.split())
    with ctx.rt.lock:
        link = load(ctx)
        live = link.state == "pairing" and link.code_expires and datetime.fromisoformat(link.code_expires) > _wall()
        if not live or not secrets.compare_digest(_norm(body.code), link.code or ""):
            if link.state == "pairing":
                link.wrong_tries += 1
                if link.wrong_tries >= MAX_PAIR_TRIES:
                    link = Link("none")
                save(ctx, link)
            raise HTTPException(404, "wrong or expired pairing code")
        link.state, link.code_status = "consent", "consent"
        link.pending_name, link.pending_jwk = name, key.export_public()
        link.verify_code = verify_code()
        save(ctx, link)
    return link.verify_code


def agent_pass(ctx: Ctx, code: str) -> PassOut:
    link = load(ctx)
    if not link.code or not secrets.compare_digest(_norm(code), link.code) or \
            datetime.fromisoformat(link.code_expires) <= _wall() or link.code_status not in ("consent", "allowed", "denied"):
        raise HTTPException(404, "wrong or expired pairing code")
    if link.code_status == "allowed":
        return PassOut(status="allowed", spend_pass=seed.issuance(ctx.db_path))
    return PassOut(status=link.code_status)


def allow(ctx: Ctx) -> None:
    """Sign M-1 to the waiting agent's key. When that is the key Validio holds for the connector URL, the URL
    stays valid and its token is no longer kept in clear; any other agent ends the connector URL."""
    with ctx.rt.lock:
        link = load(ctx)
        if link.state != "consent":
            raise HTTPException(409, "no agent waits for consent")
        key = JWK.from_json(link.pending_jwk)
        demo = key.thumbprint() == demo_key(ctx).thumbprint()
        sub = DEMO_CLAIMS["sub"] if demo else "agent:" + ("".join(ch if ch.isalnum() else "-" for ch in
                                                                   link.pending_name.lower()).strip("-") or "agent")
        seed.sign_again(ctx.db_path, ctx.keys_dir, {"sub": sub}, agent_pub=key, why="Agent connected", at=ctx.now())
        ver = seed.pass_version(ctx.db_path, seed.SPEND_PASS_ID)
        link = Link("active", link.pending_name, sub, key.export_public(), key_id(key), ctx.now().isoformat(),
                    code=link.code, code_expires=link.code_expires, code_status="allowed")
        save(ctx, link)
        held = _connector(ctx)
        if held and JWK.from_json(held[0]).thumbprint() == key.thumbprint():
            _set_connector(ctx, held[0], held[1], None)
        else:
            drop_connector(ctx)
        _entry(ctx, f"Connected {link.name}. Spend Pass {seed.SPEND_PASS_ID} is now version {ver}, signed to its key.")


def deny(ctx: Ctx) -> None:
    with ctx.rt.lock:
        link = load(ctx)
        if link.state not in ("consent", "pairing"):
            raise HTTPException(409, "no agent waits for consent")
        save(ctx, Link("none", code=link.code, code_expires=link.code_expires, code_status="denied"))
        drop_connector(ctx)


def pause(ctx: Ctx, paused: bool) -> None:
    with ctx.rt.lock:
        link = load(ctx)
        if link.state not in ("active", "paused"):
            raise HTTPException(409, "no agent is connected")
        state = "paused" if paused else "active"
        if link.state == state:
            return
        link.state = state
        save(ctx, link)
        _entry(ctx, f"{'Paused' if paused else 'Resumed'} {link.name}.")


def disconnect(ctx: Ctx, quiet: bool = False) -> None:
    """Sign M-1 again to a key nobody keeps: the agent's copy is superseded, the id stays usable. `quiet` writes
    no ledger entry (a new account that starts without an agent)."""
    with ctx.rt.lock:
        link = load(ctx)
        nobody = JWK.generate(kty="EC", crv="P-256")
        seed.sign_again(ctx.db_path, ctx.keys_dir, {}, agent_pub=JWK.from_json(nobody.export_public()),
                        why="Agent disconnected", at=ctx.now())
        save(ctx, Link("none"))
        drop_connector(ctx)
        if not quiet and link.state in ("active", "paused"):
            ver = seed.pass_version(ctx.db_path, seed.SPEND_PASS_ID)
            _entry(ctx, f"Disconnected {link.name}. Spend Pass {seed.SPEND_PASS_ID} is now version {ver}, "
                        "the agent's copy is refused.")


def check_use(ctx: Ctx, m: Mandate, token: str | None = None) -> None:
    """Called after every verified pass. On an account the pass must be the very copy it signed last: demo copies
    share the template's kitchen key, so a signature alone does not say which kitchen it came from (each
    signing is unique, so the issuer JWT does). M-1 is the connected agent's: refused while paused (one ledger
    entry per refusal), its last use noted otherwise."""
    # accounts only: the local kitchen keeps a pass valid across `make seed` (seed.reset), on purpose
    if ctx.account is not None and token is not None and token.split("~", 1)[0] != _issued_jwt(ctx, m.id):
        raise MandateError(f"Spend Pass {m.id} was not signed by this kitchen")
    if m.id != seed.SPEND_PASS_ID:
        return
    with ctx.rt.lock:
        link = load(ctx)
        if link.state not in ("active", "paused"):
            raise MandateError(NOT_CONNECTED)
        if link.state == "paused":
            _entry(ctx, f"Refused {link.name}: {PAUSED}.", actor="validio:gate")
            raise MandateError(PAUSED)
        if link.state == "active":
            link.last_used_at = ctx.now().isoformat()
            save(ctx, link)


def _issued_jwt(ctx: Ctx, pass_id: str) -> str | None:
    con = sqlite3.connect(ctx.db_path, timeout=10)
    try:
        row = con.execute("select issuance from spend_pass where id = ?", (pass_id,)).fetchone()
    finally:
        con.close()
    return row[0].split("~", 1)[0] if row else None


# Any MCP agent, also one that cannot sign (a chat app connector, a coding tool, a script): pairing makes an
# agent key Validio holds for this kitchen and a connector token, shown as /mcp/c/<token>/. The first request
# there asks for consent as "MCP agent"; after Allow Validio signs the key binding itself on every call. The
# token is kept in clear only while pairing waits; an index in the accounts db finds the kitchen by its hash.

CONNECTOR_SCHEMA = """create table if not exists connector (
  id integer primary key check (id = 1), private_jwk text not null, token_hash text not null, token text)"""
INDEX_SCHEMA = "create table if not exists connector_index (token_hash text primary key, account_id text)"
WAITING = ("Waiting for the kitchen to press Allow in Validio. Ask the user to open the Agent page in Validio "
           "and press Allow, then call the tool again.")
WAITING_CODE = ("Waiting for the kitchen to press Allow in Validio. Show the user this verification code: {code}. "
                "It must match the code on the Validio Agent page. Ask the user to open the Agent page in Validio, "
                "check that the codes match and press Allow, then call the tool again.")


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _kcon(ctx: Ctx) -> sqlite3.Connection:
    con = sqlite3.connect(ctx.db_path, timeout=10)
    con.execute("pragma secure_delete = on")  # a token cleared after Allow leaves no copy in free pages
    con.execute(CONNECTOR_SCHEMA)
    return con


def _connector(ctx: Ctx) -> tuple[str, str, str | None] | None:
    """(private JWK json, token hash, token while pairing waits) of the key Validio holds, or None."""
    con = _kcon(ctx)
    try:
        return con.execute("select private_jwk, token_hash, token from connector where id = 1").fetchone()
    finally:
        con.close()


def _index(ctx: Ctx, token_hash: str | None) -> None:
    """Point the token's hash at this kitchen (None drops the kitchen's entry). The local kitchen keeps no
    index entry: a token not in the index is looked up in the local store."""
    acct = account_id(ctx)
    if acct is None:
        return
    from .accounts import get_accounts

    with get_accounts()._db() as con:
        con.execute(INDEX_SCHEMA)
        con.execute("delete from connector_index where account_id = ?", (acct,))
        if token_hash:
            con.execute("insert into connector_index values (?, ?)", (token_hash, acct))


def _set_connector(ctx: Ctx, private_jwk: str, token_hash: str, token: str | None) -> None:
    con = _kcon(ctx)
    try:
        con.execute("insert or replace into connector (id, private_jwk, token_hash, token) values (1, ?, ?, ?)",
                    (private_jwk, token_hash, token))
        con.commit()
    finally:
        con.close()
    _index(ctx, token_hash)


def drop_connector(ctx: Ctx) -> None:
    """Forget the held key and the token: /mcp/c/<token>/ answers 404 from now on."""
    con = _kcon(ctx)
    try:
        had = con.execute("delete from connector").rowcount
        con.commit()
    finally:
        con.close()
    if had:
        _index(ctx, None)


def connector_key(ctx: Ctx, link: Link | None = None) -> JWK | None:
    """The held private key when it is the connected agent's key, else None."""
    link = link or load(ctx)
    held = _connector(ctx)
    if not held or link.state not in ("active", "paused"):
        return None
    key = JWK.from_json(held[0])
    return key if key_id(key) == link.key_id else None


def connector_ctx(token: str | None, touch: bool = False) -> Ctx | None:
    """The kitchen a connector token belongs to while it lasts (pairing, consent, active or paused), else None.
    `touch`: a request came in on the URL, so a waiting pairing turns into consent for "MCP agent"."""
    from .accounts import get_accounts
    from .state import get_ctx

    if not token or len(token) > 128:
        return None
    h = _token_hash(token)
    accounts = get_accounts()
    with accounts._db() as con:
        con.execute(INDEX_SCHEMA)
        row = con.execute("select account_id from connector_index where token_hash = ?", (h,)).fetchone()
    try:
        ctx = accounts.ctx(row[0]) if row else get_ctx()
    except KeyError:
        return None
    held = _connector(ctx)
    if not held or not secrets.compare_digest(held[1], h):
        return None
    link = load(ctx)
    if link.state in ("active", "paused") and connector_key(ctx, link) is None:
        return None
    if link.state == "none":
        return None
    if touch and link.state == "pairing":
        with ctx.rt.lock:
            link = load(ctx)
            if link.state == "pairing":
                link.state, link.code_status = "consent", "consent"
                link.pending_name = MCP_NAME
                link.pending_jwk = JWK.from_json(held[0]).export_public()
                link.verify_code = verify_code()  # new for this connection, shown in the agent and on the page
                save(ctx, link)
    return ctx


def connector_waiting(ctx: Ctx) -> bool:
    """The kitchen has not allowed the connector's key yet."""
    return connector_key(ctx) is None


def consent_code(ctx: Ctx) -> str | None:
    """The verification code of the connection that waits for consent, made now for a consent from before
    codes existed; None when nothing waits."""
    link = load(ctx)
    if link.state != "consent":
        return None
    if not link.verify_code:
        with ctx.rt.lock:
            link = load(ctx)
            if link.state == "consent" and not link.verify_code:
                link.verify_code = verify_code()
                save(ctx, link)
    return link.verify_code


def waiting_text(ctx: Ctx) -> str:
    """What every connector tool answers while the kitchen has not pressed Allow."""
    code = consent_code(ctx)
    return WAITING_CODE.format(code=code) if code else WAITING


def connector_presentation(ctx: Ctx) -> str:
    """The Spend Pass presented with the held key and a fresh nonce, as the agent's own holder would."""
    from ..agent.holder import Holder
    from . import tools

    key = connector_key(ctx)
    if key is None:
        raise MandateError(NOT_CONNECTED)
    return Holder(seed.issuance(ctx.db_path), key, lambda: tools.nonce(ctx)).presentation()


# routes


def web_router() -> APIRouter:
    """/api/agent/* behind the same gate and ctx as every /api route."""
    from . import ui

    r = APIRouter(prefix="/api", tags=["web"], dependencies=[Depends(ui.kitchen)])
    Dep = ui.CtxDep

    @r.get("/agent", response_model=AgentState, response_model_exclude_none=True)
    def get_agent(ctx: Dep, request: Request):
        return view(ctx, request)

    @r.post("/agent/pair", response_model=AgentState, response_model_exclude_none=True)
    def pair_route(ctx: Dep, request: Request):
        return view(ctx, request, pair(ctx))

    @r.post("/agent/allow", response_model=AgentState, response_model_exclude_none=True)
    def allow_route(ctx: Dep, request: Request):
        allow(ctx)
        return view(ctx, request)

    @r.post("/agent/deny", response_model=AgentState, response_model_exclude_none=True)
    def deny_route(ctx: Dep, request: Request):
        deny(ctx)
        return view(ctx, request)

    @r.post("/agent/pause", response_model=AgentState, response_model_exclude_none=True)
    def pause_route(ctx: Dep, request: Request, body: PauseIn):
        pause(ctx, body.paused)
        return view(ctx, request)

    @r.post("/agent/disconnect", response_model=AgentState, response_model_exclude_none=True)
    def disconnect_route(ctx: Dep, request: Request):
        disconnect(ctx)
        return view(ctx, request)

    return r


def agent_routes(r: APIRouter, Dep, suffix: str = "") -> None:
    """The agent's side of pairing, added to an /agent/v1 router."""

    @r.post("/pair", status_code=202, response_model=PairOut, operation_id=f"pair_agent{suffix}")
    def pair_agent(ctx: Dep, body: PairIn):
        """Answer the kitchen's pairing code with the agent's name and public P-256 key. The kitchen then
        sees the consent screen."""
        return PairOut(status="consent", verify_code=agent_pair(ctx, body))

    @r.get("/pass", response_model=PassOut, response_model_exclude_none=True, operation_id=f"get_pass{suffix}")
    def get_pass(ctx: Dep, code: str):
        """Poll with the pairing code: consent (still waiting), allowed (with the Spend Pass) or denied."""
        return agent_pass(ctx, code)
