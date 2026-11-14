"""Kitchen accounts: signup, login, sessions, the demo kitchen per browser, and one store per account.

accounts.db (VALIDIO_ACCOUNTS, default data/accounts/) holds the accounts and the sessions. Each account has
its own directory there with validio.db and keys/, copied from the template (VALIDIO_TEMPLATE, default
data/template/) when one was built, seeded fresh otherwise. Passwords and approval codes are scrypt hashes,
sessions are stored as sha256 of the cookie value. See docs/ACCOUNTS-API.md.
"""

import hashlib
import hmac
import os
import re
import secrets
import shutil
import sqlite3
import threading
import time
from collections import OrderedDict
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import Field

from ..demo import seed
from .connect import AgentState
from .schemas import Model
from .state import Ctx, get_ctx
from .steady import Runtime

COOKIE = "validio_session"
SESSION_SECONDS = 12 * 3600
DEMO_CODE = "246810"
DEMO_NAME = "Hotel Espoo kitchen"
DEMO_CUSTOMER = "hotel-espoo"
DEMO_MAX_AGE = 48 * 3600
MAX_OPEN = 64
LOGIN_TRIES, LOGIN_WINDOW = 5, 15 * 60

SCHEMA = """
create table if not exists account (
  id text primary key, name text not null, email text unique, pw_hash text, code_hash text not null,
  customer text not null, address text not null default '', is_demo integer not null default 0,
  rules_saved integer not null default 0, created_at real not null);
create table if not exists session (id_hash text primary key, account_id text not null, expires real not null);
"""


def accounts_dir() -> Path:
    return Path(os.environ.get("VALIDIO_ACCOUNTS") or seed.DATA / "accounts")


def template_dir() -> Path:
    return Path(os.environ.get("VALIDIO_TEMPLATE") or seed.DATA / "template")


# scrypt from the standard library: n=2**14, r=8, p=1 (about 16 MB, a few ms)


def hash_secret(secret: str) -> str:
    salt = secrets.token_bytes(16)
    h = hashlib.scrypt(secret.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${h.hex()}"


def secret_ok(secret: str, stored: str | None) -> bool:
    try:
        kind, salt, h = (stored or "").split("$")
    except ValueError:
        return False
    if kind != "scrypt":
        return False
    got = hashlib.scrypt(secret.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1, dklen=32)
    return hmac.compare_digest(got.hex(), h)


def _sid_hash(sid: str) -> str:
    return hashlib.sha256(sid.encode()).hexdigest()


class Accounts:
    """The account rows and an LRU of open stores, one Ctx per account. Every Ctx shares the catalog and the
    Valio client of the local runtime; each has its own db, keys, lock, nonces and code tries."""

    def __init__(self, root: Path | None = None, template: Path | None = None, shared: Runtime | None = None):
        self.root = Path(root or accounts_dir())
        self.template = Path(template or template_dir())
        self.shared = shared or get_ctx().rt
        self.lock = threading.RLock()
        self.open: OrderedDict[str, Ctx] = OrderedDict()
        self.root.mkdir(parents=True, exist_ok=True)
        with self._db() as con:
            con.executescript(SCHEMA)

    def _db(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.root / "accounts.db", timeout=10)
        con.row_factory = sqlite3.Row
        return con

    # rows

    def get(self, account_id: str) -> dict | None:
        with self._db() as con:
            row = con.execute("select * from account where id = ?", (account_id,)).fetchone()
        return dict(row) if row else None

    def by_email(self, email: str) -> dict | None:
        with self._db() as con:
            row = con.execute("select * from account where email = ?", (email.lower(),)).fetchone()
        return dict(row) if row else None

    def update(self, account_id: str, **fields) -> None:
        cols = ", ".join(f"{k} = ?" for k in fields)
        with self._db() as con:
            con.execute(f"update account set {cols} where id = ?", (*fields.values(), account_id))

    def create(self, *, name: str, email: str | None, password: str | None, customer: str, code: str,
               is_demo: bool = False) -> dict:
        from . import codes
        from .settings import _put

        account_id = f"k-{secrets.token_hex(4)}"
        self._copy_store(account_id)
        db, _keys = self.paths(account_id)
        codes.store(db, code)  # the kitchen's own code lives in its store (api/codes.py), Settings changes it there
        _put(db, {"kitchen_name": name} | ({} if is_demo else {"rules_saved": "0"}))
        try:
            with self._db() as con:
                con.execute("insert into account (id, name, email, pw_hash, code_hash, customer, is_demo, "
                            "rules_saved, created_at) values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (account_id, name, email.lower() if email else None,
                             hash_secret(password) if password else None, hash_secret(code), customer,
                             int(is_demo), int(is_demo), time.time()))
        except sqlite3.IntegrityError:
            shutil.rmtree(self.root / account_id, ignore_errors=True)
            raise
        return self.get(account_id)

    def delete(self, account_id: str) -> None:
        with self.lock:
            c = self.open.pop(account_id, None)
            if c is not None:
                c.rt.close()
        with self._db() as con:
            con.execute("delete from session where account_id = ?", (account_id,))
            con.execute("delete from account where id = ?", (account_id,))
        shutil.rmtree(self.root / account_id, ignore_errors=True)

    def sweep(self, now: float | None = None) -> list[str]:
        """Demo copies older than 48 h go, with their sessions and files."""
        cutoff = (now or time.time()) - DEMO_MAX_AGE
        with self._db() as con:
            old = [r[0] for r in con.execute("select id from account where is_demo = 1 and created_at < ?", (cutoff,))]
            con.execute("delete from session where expires < ?", (now or time.time(),))
        for a in old:
            self.delete(a)
        return old

    # stores

    def paths(self, account_id: str) -> tuple[Path, Path]:
        d = self.root / account_id
        return d / "validio.db", d / "keys"

    def _copy_store(self, account_id: str) -> None:
        """The template's db and keys (the ledger head and the pass are signed with that kitchen key, so they go
        together), or a fresh seed when no template was built. Either way no agent is connected yet:
        the person connects one (the demo copy too, "Connect the demo agent")."""
        db, keys = self.paths(account_id)
        from .connect import leave_unconnected

        self._copy_files(db, keys)
        leave_unconnected(db)

    def _copy_files(self, db: Path, keys: Path) -> None:
        db.parent.mkdir(parents=True, exist_ok=True)
        if keys.exists():
            shutil.rmtree(keys)
        tdb, tkeys = self.template / "validio.db", self.template / "keys"
        if seed.seed_token(tdb) is None or not tkeys.is_dir():
            if db.exists():
                db.unlink()
            seed.reset(db, keys)
            return
        src, dst = sqlite3.connect(tdb), sqlite3.connect(db)
        try:
            src.backup(dst)
        finally:
            src.close()
            dst.close()
        shutil.copytree(tkeys, keys)
        # a new token, so a runtime that had this path open (after a reset) reopens its stores
        con = sqlite3.connect(db)
        try:
            with con:
                con.execute("update demo_state set value = ? where key = 'seed_token'", (secrets.token_hex(8),))
        finally:
            con.close()

    def ctx(self, account_id: str) -> Ctx:
        with self.lock:
            c = self.open.get(account_id)
            if c is not None:
                self.open.move_to_end(account_id)
                return c
            row = self.get(account_id)
            if row is None:
                raise KeyError(account_id)
            db, keys = self.paths(account_id)
            rt = Runtime(db, keys, shared=self.shared)

            def code_ok(given: str, _id=account_id) -> bool:
                return bool(re.fullmatch(r"\d{6}", given)) and secret_ok(given, (self.get(_id) or {}).get("code_hash"))

            def reseed(_id=account_id, _rt=rt) -> None:
                _rt.close()
                self._copy_store(_id)

            c = Ctx(rt, account=row, code_ok=code_ok, reseed=reseed)
            self.open[account_id] = c
            while len(self.open) > MAX_OPEN:
                _, old = self.open.popitem(last=False)
                old.rt.close()
            return c

    # sessions

    def start_session(self, account_id: str) -> str:
        sid = secrets.token_urlsafe(32)
        with self._db() as con:
            con.execute("insert into session values (?, ?, ?)", (_sid_hash(sid), account_id, time.time() + SESSION_SECONDS))
        return sid

    def end_session(self, sid: str) -> None:
        with self._db() as con:
            con.execute("delete from session where id_hash = ?", (_sid_hash(sid),))

    def session_account(self, sid: str | None) -> str | None:
        if not sid:
            return None
        with self._db() as con:
            row = con.execute("select account_id, expires from session where id_hash = ?", (_sid_hash(sid),)).fetchone()
        if row is None or row["expires"] < time.time():
            return None
        return row["account_id"]


_accounts: Accounts | None = None
_accounts_lock = threading.Lock()


def get_accounts() -> Accounts:
    """One registry per process; a test that changes VALIDIO_ACCOUNTS gets a fresh one."""
    global _accounts
    with _accounts_lock:
        if _accounts is None or _accounts.root != accounts_dir() or _accounts.template != template_dir():
            _accounts = Accounts(shared=get_ctx().rt)  # the local kitchen's catalog and Valio client
        return _accounts


def session_account_id(request: Request) -> str | None:
    acc = get_accounts()
    a = acc.session_account(request.cookies.get(COOKIE))
    return a if a and acc.get(a) else None


def request_ctx(request: Request) -> Ctx:
    """The Ctx a web request works on: the session's account, else the local kitchen (`get_ctx()`), which
    the gate in ui.kitchen only lets callers on this machine reach."""
    a = session_account_id(request)
    if a is not None:
        return get_accounts().ctx(a)
    return get_ctx()


# the routes


class SignupIn(Model):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=200, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8, max_length=200)
    customer_number: str = Field(pattern=r"^\d{1,20}$")
    approval_code: str = Field(pattern=r"^\d{6}$")


class LoginIn(Model):
    email: str = Field(max_length=200)
    password: str = Field(max_length=200)


class SetupView(Model):
    kitchen: bool
    rules: bool
    agent: bool
    done: bool


class AccountView(Model):
    id: str
    name: str
    email: str | None
    customer_number: str
    delivery_address: str
    is_demo: bool
    demo_code: str | None = None
    setup: SetupView
    agent: AgentState
    created_at: str


router = APIRouter(prefix="/api/account", tags=["account"])
_tries: dict[str, list[float]] = {}
_tries_lock = threading.Lock()


def agent_state(row: dict):
    """The agent connection as the Agent page shows it (api/connect.py)."""
    from . import connect

    return connect.view(get_accounts().ctx(row["id"]))


def view(row: dict) -> AccountView:
    """Name, address and whether the Rules were saved come from the kitchen's store (api/settings.py writes
    them there); the row keeps what signup gave."""
    from .settings import _get, rules_saved

    db, _keys = get_accounts().paths(row["id"])
    row = {**row, "name": _get(db, "kitchen_name") or row["name"], "address": _get(db, "delivery_address") or ""}
    agent = agent_state(row)
    kitchen = bool(row["name"]) and (bool(row["address"]) or bool(row["is_demo"]))
    rules = rules_saved(db)
    connected = agent.state in ("active", "paused")
    return AccountView(
        id=row["id"], name=row["name"], email=row["email"], customer_number=row["customer"],
        delivery_address=row["address"], is_demo=bool(row["is_demo"]),
        demo_code=DEMO_CODE if row["is_demo"] else None,
        setup=SetupView(kitchen=kitchen, rules=rules, agent=connected, done=kitchen and rules and connected),
        agent=agent, created_at=datetime.fromtimestamp(row["created_at"], UTC).isoformat())


def _signed_in(request: Request, row: dict, status: int = 200) -> Response:
    sid = get_accounts().start_session(row["id"])
    r = Response(view(row).model_dump_json(by_alias=True, exclude_none=True), status_code=status,
                 media_type="application/json")
    r.set_cookie(COOKIE, sid, httponly=True, samesite="lax", secure=request.url.scheme == "https",
                 max_age=SESSION_SECONDS, path="/")
    return r


def _too_many(keys: list[str]) -> bool:
    now = time.time()
    with _tries_lock:
        for k in keys:
            _tries[k] = [t for t in _tries.get(k, []) if t > now - LOGIN_WINDOW]
        return any(len(_tries[k]) >= LOGIN_TRIES for k in keys)


def _miss(keys: list[str]) -> None:
    with _tries_lock:
        for k in keys:
            _tries.setdefault(k, []).append(time.time())


@router.post("/signup", response_model=AccountView, status_code=201, response_model_exclude_none=True)
def signup(request: Request, body: SignupIn):
    try:
        row = get_accounts().create(name=body.name.strip(), email=body.email.strip(), password=body.password,
                                    customer=body.customer_number, code=body.approval_code)
    except sqlite3.IntegrityError as e:
        raise HTTPException(409, "an account with this email exists") from e
    return _signed_in(request, row, 201)


@router.post("/login", response_model=AccountView, response_model_exclude_none=True)
def login(request: Request, body: LoginIn):
    email = body.email.strip().lower()
    keys = [f"email:{email}", f"client:{request.client.host if request.client else '?'}"]
    if _too_many(keys):
        raise HTTPException(429, "too many wrong logins, wait 15 minutes")
    row = get_accounts().by_email(email)
    if row is None or not secret_ok(body.password, row["pw_hash"]):
        _miss(keys)
        raise HTTPException(401, "wrong email or password")
    return _signed_in(request, row)


@router.post("/logout", status_code=204)
def logout(request: Request) -> Response:
    sid = request.cookies.get(COOKIE)
    if sid:
        get_accounts().end_session(sid)
    r = Response(status_code=204)
    r.delete_cookie(COOKIE, path="/")
    return r


@router.post("/demo", response_model=AccountView, response_model_exclude_none=True)
def demo(request: Request):
    """The demo kitchen: the copy this browser already has, or a fresh one from the template."""
    acc = get_accounts()
    a = session_account_id(request)
    if a is not None and acc.get(a)["is_demo"]:
        return view(acc.get(a))
    acc.sweep()
    row = acc.create(name=DEMO_NAME, email=None, password=None, customer=DEMO_CUSTOMER, code=DEMO_CODE,
                     is_demo=True)
    return _signed_in(request, row)


@router.get("", response_model=AccountView, response_model_exclude_none=True)
def account(request: Request):
    a = session_account_id(request)
    if a is None:
        raise HTTPException(401, "not logged in")
    return view(get_accounts().get(a))
