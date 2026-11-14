"""What the agent routes, the web app routes and the MCP tools share.

One runtime for the whole app: the Steady Order routes' `runtime` (api/steady.py) holds the catalog,
the Valio client and the stores, and reopens the stores when the seed token changes after a reset.
Ctx adds what only the agent side needs: nonces, the kitchen's public key, the supply pipeline, the
approval code and the kitchen token.

Public deploys (VALIDIO_PUBLIC=1) must set VALIDIO_APPROVE_CODE and VALIDIO_KITCHEN_TOKEN, or the app does
not start. Without VALIDIO_PUBLIC, a caller that is not on this machine still finds approve and the web reads
closed while those are unset. The demo switches are for demo copies (a session) and this machine only.
"""

import os
import re
import threading
from contextvars import ContextVar
from pathlib import Path

from jwcrypto.jwk import JWK

from ..config import DEFAULT_ENV, _read_env_file
from ..demo import seed
from ..orders.supply import SupplyService
from ..policy.mandate import (
    AUDIENCE,
    DEMO_CLAIMS,
    Mandate,
    NonceStore,
    load_or_create_key,
    verify_presentation,
)
from ..text.format import short_ref
from .steady import Runtime, runtime

MAX_CODE_TRIES = 5
LOOPBACK = frozenset({"127.0.0.1", "::1", "testclient"})  # testclient: Starlette's in-process client


def _env() -> dict[str, str]:
    return {**_read_env_file(DEFAULT_ENV), **os.environ}


class Ctx:
    """`account` is None for the local kitchen (VALIDIO_DB); an account's Ctx comes from api/accounts.py with its
    own runtime, the hash of its own approval code and its own reset."""

    def __init__(self, rt: Runtime = runtime, account=None, code_ok=None, reseed=None):
        self.rt = rt
        self.account = account
        self._code_ok = code_ok
        self._reseed = reseed
        env = _env()
        self.approve_code = "" if account is not None else env.get("VALIDIO_APPROVE_CODE", "")
        if self.approve_code and not re.fullmatch(r"\d{6}", self.approve_code):
            raise ValueError("VALIDIO_APPROVE_CODE must be 6 digits")
        self.code_tries: dict[tuple[str, str], int] = {}  # ("key", order or button) and ("client", host)
        self.nonces = NonceStore()
        self._supply: tuple[object, SupplyService] | None = None
        self._kitchen: tuple[Path, JWK] | None = None

    @property
    def has_code(self) -> bool:
        from . import codes

        return self._code_ok is not None or bool(self.approve_code) or codes.stored(self.db_path) is not None

    def code_ok(self, given: str | None) -> bool:
        """The account's code (hash in its row); for the local kitchen a code set in Settings (api/codes.py),
        else VALIDIO_APPROVE_CODE."""
        import hmac

        from . import codes

        if self._code_ok is not None:
            return self._code_ok(given or "")
        own = codes.stored(self.db_path)
        if own is not None:
            return codes.matches(own, given)
        return hmac.compare_digest((given or "").encode(), self.approve_code.encode())

    # read on every call, so a test or an operator can change them without a restart

    @property
    def public(self) -> bool:
        return _env().get("VALIDIO_PUBLIC", "") == "1"

    @property
    def public_read(self) -> bool:
        """GET routes of the web API open to anyone (the public demo); writes stay behind the gates."""
        return _env().get("VALIDIO_PUBLIC_READ", "") == "1"

    @property
    def kitchen_token(self) -> str:
        return _env().get("VALIDIO_KITCHEN_TOKEN", "")

    @property
    def mcp_hosts(self) -> list[str]:
        """Extra Host names MCP answers on (the Modal hostname), next to 127.0.0.1 and localhost."""
        return [h.strip() for h in _env().get("VALIDIO_MCP_HOSTS", "").split(",") if h.strip()]

    def is_local(self, host: str | None) -> bool:
        """A caller on this machine. On a public deploy nobody is, whatever the proxy in front says."""
        return not self.public and host in LOOPBACK

    def startup_problems(self) -> list[str]:
        if not self.public:
            return []
        missing = [k for k, v in (("VALIDIO_APPROVE_CODE", self.approve_code),
                                  ("VALIDIO_KITCHEN_TOKEN", self.kitchen_token)) if not v]
        return missing

    @property
    def settings(self):
        return self.rt.settings

    @property
    def catalog(self):
        return self.rt.catalog

    @property
    def valio(self):
        return self.rt.valio

    @property
    def live(self):
        with self.rt.lock:
            return self.rt.live()

    @property
    def db_path(self) -> Path:
        return self.live.path

    @property
    def keys_dir(self) -> Path:
        return self.rt.keys_dir()

    @property
    def store(self):
        return self.live.store

    @property
    def audit(self):
        return self.live.audit

    @property
    def orders(self):
        return self.live.service

    @property
    def supply(self) -> SupplyService:
        svc = self.orders
        if self._supply is None or self._supply[0] is not svc:
            from ..reader import read

            audit = svc.audit
            self._supply = (svc, SupplyService(svc, reader=lambda text, pid: read(
                text, ledger=audit, now=svc.clock(), product_id=pid).result))
        return self._supply[1]

    def now(self):
        return self.orders.clock()

    @property
    def kitchen_pub(self) -> JWK:
        path = self.keys_dir / "kitchen-es256.json"
        if self._kitchen is None or self._kitchen[0] != path:
            self._kitchen = (path, JWK.from_json(load_or_create_key(path).export_public()))
        return self._kitchen[1]

    def reset(self, fresh: bool = False) -> None:
        """`fresh` on an account: the seed of `make seed` in its own store and keys instead of the template, with no
        agent connected (the live e2e starts every run from there, also against the public link)."""
        with self.rt.lock:
            if fresh and self.account is not None:
                from .connect import leave_unconnected

                self.rt.close()
                seed.reset(self.db_path, self.keys_dir)
                leave_unconnected(self.db_path)
            elif self._reseed is not None:
                self._reseed()
            else:
                seed.reset(self.db_path, self.keys_dir)
            self.code_tries.clear()
            self.nonces = NonceStore()

    def real_stock(self) -> tuple[float, str] | None:
        """466375 as Valio answers it, read at request time (replayed in the demo)."""
        return seed.real_stock(self.valio)

    def stockout(self) -> bool:
        return seed.stockout(self.db_path)

    def set_stockout(self, on: bool) -> None:
        with self.rt.lock:
            self._set_stockout(on)

    def _set_stockout(self, on: bool) -> None:
        seed.set_stockout(self.db_path, on)
        if on:
            self.audit.append(at=self.now(), actor="presenter", kind="simulation",
                              sentence=seed.stockout_note(self.real_stock(),
                                                          f"Simulated a stock-out of {self._stockout_name()} "
                                                          "for the demo."),
                              facts=[], mandate_id=None, disclosed={}, rule_ids=[], order_id=None)
        else:
            self.audit.append(at=self.now(), actor="presenter", kind="simulation",
                              sentence=seed.stockout_note(self.real_stock(),
                                                          f"Ended the simulated stock-out of {self._stockout_name()}.")
                              .replace("Valio really has stock.", "Valio has stock."),
                              facts=[], mandate_id=None, disclosed={}, rule_ids=[], order_id=None)

    def valio_down(self) -> bool:
        return seed.valio_down(self.db_path)

    def set_valio_down(self, on: bool) -> None:
        """The demo switch "Valio not answering", with one simulation entry per change."""
        with self.rt.lock:
            seed.set_valio_down(self.db_path, on)
            sentence = ("Simulated Valio not answering for the demo. Every request is refused until it ends."
                        if on else "Ended the simulated Valio outage. Valio answers again.")
            self.audit.append(at=self.now(), actor="presenter", kind="simulation", sentence=sentence,
                              facts=[], mandate_id=None, disclosed={}, rule_ids=[], order_id=None)

    def _stockout_name(self) -> str:
        p = self.catalog.get(seed.STOCKOUT_ID)
        return short_ref(p.name_en) if p else seed.STOCKOUT_ID

    def verify(self, token: str) -> Mandate:
        from .connect import check_use

        m = verify_presentation(token, kitchen_pub=self.kitchen_pub, issuer=DEMO_CLAIMS["iss"], aud=AUDIENCE,
                                   nonces=self.nonces, now=self.now(), revoked=self.store.is_revoked,
                                   version=lambda jti: seed.pass_version(self.db_path, jti))
        check_use(self, m, token)  # a paused agent is refused here, with a ledger entry
        return m


_ctx: Ctx | None = None
_ctx_lock = threading.Lock()
# the account a piece of code runs for when no request is at hand (an in-process MCP client)
current: ContextVar[Ctx | None] = ContextVar("validio_ctx", default=None)


def get_ctx() -> Ctx:
    """The Ctx set in `current`, else the local kitchen (or the one a test pinned with set_ctx)."""
    c = current.get()
    if c is not None:
        return c
    global _ctx
    with _ctx_lock:
        if _ctx is None:
            _ctx = Ctx()
        return _ctx


def set_ctx(ctx: Ctx | None) -> None:
    global _ctx
    _ctx = ctx
