"""The agent interface under /agent/v1 (OpenAPI 3.1). Writes need `Authorization: SD-JWT <presentation>`.

The same routes twice: /agent/v1/... for the local kitchen (`make demo`, the tests) and
/agent/v1/k/{account}/... for a kitchen account, each on that kitchen's own store. The per-account copies stay
out of the OpenAPI document; docs/AGENTS.md names the prefix."""

import re
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request

from . import connect, tools
from .limits import NONCES, client_ip
from .schemas import ConfirmIn, NonceView, OrderView, ProductSummary, SupplyRequestIn, SupplyRequestView
from .state import Ctx, get_ctx

ACCOUNT_ID = re.compile(r"k-(?:[0-9a-f]{32}|[0-9a-f]{8})")  # 8: accounts made before the ids grew
Auth = Annotated[str | None, Header(alias="Authorization", description="SD-JWT <presentation>")]


def account_ctx(account: str) -> Ctx:
    """The kitchen named in the path; 404 for one that does not exist."""
    from .accounts import get_accounts

    if not ACCOUNT_ID.fullmatch(account):
        raise HTTPException(404, f"no kitchen {account}")
    try:
        return get_accounts().ctx(account)
    except KeyError as e:
        raise HTTPException(404, f"no kitchen {account}") from e


def _read_gate(ctx: Ctx, authorization: str | None, suffix: str) -> None:
    """Reads on a kitchen's own path need its pass: the account id is in every URL the kitchen hands out, so it is
    no secret. The local kitchen's reads stay open, as before. A pass sent anyway is checked."""
    if suffix or authorization:
        ctx.verify(tools.bearer(authorization))


def _routes(router: APIRouter, CtxDep, suffix: str = "") -> APIRouter:
    @router.get("/products", response_model=list[ProductSummary], operation_id=f"search_products{suffix}")
    def search_products(ctx: CtxDep, q: str | None = None, category: str | None = None,
                        claims: Annotated[list[str] | None, Query()] = None,
                        limit: Annotated[int, Query(ge=1, le=20)] = 10):
        """Products from Valio's catalog with graded claims. Static data only, no live call.
        Supplier text sits in descriptionUntrusted and is never used for a decision."""
        return tools.search_products(ctx, q, category, claims, limit)


    @router.get("/nonce", response_model=NonceView, operation_id=f"get_nonce{suffix}")
    def get_nonce(ctx: CtxDep, request: Request):
        """A fresh single-use nonce for the Spend Pass key binding. At most 120 a minute per client."""
        kitchen = ctx.account["id"] if ctx.account else "local"
        NONCES.check(f"{kitchen}:{client_ip(request)}", "nonces")
        return tools.nonce(ctx)


    @router.post("/requests", response_model=SupplyRequestView, operation_id=f"request_supply{suffix}")
    def request_supply(ctx: CtxDep, body: SupplyRequestIn, authorization: Auth = None):
        """Text or typed lines in, ranked options and the Hard Lines decision out. A retry with the
        same idempotency key returns the same request."""
        return tools.request_supply(ctx, tools.bearer(authorization), body)


    @router.get("/requests/{request_id}", response_model=SupplyRequestView, operation_id=f"get_request{suffix}")
    def get_request(ctx: CtxDep, request_id: str, authorization: Auth = None):
        _read_gate(ctx, authorization, suffix)
        return tools.get_request(ctx, request_id)


    @router.post("/orders", response_model=OrderView, operation_id=f"confirm_order{suffix}")
    def confirm_order(ctx: CtxDep, body: ConfirmIn, authorization: Auth = None):
        """Confirm the chosen products and amounts. Validio asks Valio again for every price, the
        agent's numbers are never read."""
        return tools.confirm_order(ctx, tools.bearer(authorization), body)


    @router.get("/orders/{order_id}", response_model=OrderView, operation_id=f"get_order{suffix}")
    def get_order(ctx: CtxDep, order_id: str, authorization: Auth = None):
        _read_gate(ctx, authorization, suffix)
        return tools.get_order(ctx, order_id)
    connect.agent_routes(router, CtxDep, suffix)
    return router


router = _routes(APIRouter(prefix="/agent/v1", tags=["agent"]), Annotated[Ctx, Depends(get_ctx)])
account_router = _routes(APIRouter(prefix="/agent/v1/k/{account}", tags=["agent"], include_in_schema=False),
                         Annotated[Ctx, Depends(account_ctx)], "_k")
