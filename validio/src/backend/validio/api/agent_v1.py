"""The agent interface under /agent/v1 (OpenAPI 3.1). Writes need `Authorization: SD-JWT <presentation>`."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query

from . import connect, tools
from .schemas import ConfirmIn, NonceView, OrderView, ProductSummary, SupplyRequestIn, SupplyRequestView
from .state import Ctx, get_ctx

router = APIRouter(prefix="/agent/v1", tags=["agent"])
CtxDep = Annotated[Ctx, Depends(get_ctx)]
Auth = Annotated[str | None, Header(alias="Authorization", description="SD-JWT <presentation>")]


@router.get("/products", response_model=list[ProductSummary], operation_id="search_products")
def search_products(ctx: CtxDep, q: str | None = None, category: str | None = None,
                    claims: Annotated[list[str] | None, Query()] = None,
                    limit: Annotated[int, Query(ge=1, le=20)] = 10):
    """Products from Valio's catalog with graded claims. Static data only, no live call.
    Supplier text sits in descriptionUntrusted and is never used for a decision."""
    return tools.search_products(ctx, q, category, claims, limit)


@router.get("/nonce", response_model=NonceView, operation_id="get_nonce")
def get_nonce(ctx: CtxDep):
    """A fresh single-use nonce for the Spend Pass key binding."""
    return tools.nonce(ctx)


@router.post("/requests", response_model=SupplyRequestView, operation_id="request_supply")
def request_supply(ctx: CtxDep, body: SupplyRequestIn, authorization: Auth = None):
    """Text or typed lines in, ranked options and the Hard Lines decision out. A retry with the
    same idempotency key returns the same request."""
    return tools.request_supply(ctx, tools.bearer(authorization), body)


@router.get("/requests/{request_id}", response_model=SupplyRequestView, operation_id="get_request")
def get_request(ctx: CtxDep, request_id: str):
    return tools.get_request(ctx, request_id)


@router.post("/orders", response_model=OrderView, operation_id="confirm_order")
def confirm_order(ctx: CtxDep, body: ConfirmIn, authorization: Auth = None):
    """Confirm the chosen products and amounts. Validio asks Valio again for every price, the
    agent's numbers are never read."""
    return tools.confirm_order(ctx, tools.bearer(authorization), body)


@router.get("/orders/{order_id}", response_model=OrderView, operation_id="get_order")
def get_order(ctx: CtxDep, order_id: str):
    return tools.get_order(ctx, order_id)


connect.agent_routes(router, CtxDep)
