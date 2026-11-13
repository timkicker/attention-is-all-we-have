"""What the agent routes, the web app routes and the MCP tools share.

One runtime for the whole app: the Steady Order routes' `runtime` (api/steady.py) holds the catalog,
the Valio client and the stores, and reopens the stores when the seed token changes after a reset.
Ctx adds what only the agent side needs: nonces, the kitchen's public key, the supply pipeline, the
approval code and the demo token.
"""

import os
import re
import threading
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
from .steady import Runtime, runtime

MAX_CODE_TRIES = 5


class Ctx:
    def __init__(self, rt: Runtime = runtime):
        self.rt = rt
        env = {**_read_env_file(DEFAULT_ENV), **os.environ}
        self.approve_code = env.get("VALIDIO_APPROVE_CODE", "")
        if self.approve_code and not re.fullmatch(r"\d{6}", self.approve_code):
            raise ValueError("VALIDIO_APPROVE_CODE must be 6 digits")
        self.demo_token = env.get("VALIDIO_DEMO_TOKEN", "")
        self.code_tries: dict[str, int] = {}
        self.nonces = NonceStore()
        self._supply: tuple[object, SupplyService] | None = None
        self._kitchen: tuple[Path, JWK] | None = None

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
        return seed.keys_path()

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
            self._supply = (svc, SupplyService(svc, reader=lambda text: read(text, ledger=audit,
                                                                             now=svc.clock()).result))
        return self._supply[1]

    def now(self):
        return self.orders.clock()

    @property
    def kitchen_pub(self) -> JWK:
        path = self.keys_dir / "kitchen-es256.json"
        if self._kitchen is None or self._kitchen[0] != path:
            self._kitchen = (path, JWK.from_json(load_or_create_key(path).export_public()))
        return self._kitchen[1]

    def reset(self) -> None:
        with self.rt.lock:
            seed.reset(self.db_path, self.keys_dir)
            self.code_tries.clear()
            self.nonces = NonceStore()

    def stockout(self) -> bool:
        return seed.stockout(self.db_path)

    def set_stockout(self, on: bool) -> None:
        seed.set_stockout(self.db_path, on)
        if on:
            self.audit.append(at=self.now(), actor="presenter", kind="simulation",
                              sentence=f"Simulated a stock-out of {seed.STOCKOUT_ID}. Valio really has it in stock, "
                                       "the demo button sets it to zero.",
                              facts=[], mandate_id=None, disclosed={}, rule_ids=[], order_id=None)

    def verify(self, token: str) -> Mandate:
        return verify_presentation(token, kitchen_pub=self.kitchen_pub, issuer=DEMO_CLAIMS["iss"], aud=AUDIENCE,
                                   nonces=self.nonces, now=self.now())


_ctx: Ctx | None = None
_ctx_lock = threading.Lock()


def get_ctx() -> Ctx:
    global _ctx
    with _ctx_lock:
        if _ctx is None:
            _ctx = Ctx()
        return _ctx


def set_ctx(ctx: Ctx | None) -> None:
    global _ctx
    _ctx = ctx
