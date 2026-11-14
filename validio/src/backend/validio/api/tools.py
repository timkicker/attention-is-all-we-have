"""The five agent tools as plain functions. The HTTP routes under /agent/v1 and the MCP server both
call these, so there is one code path. Writes take the Spend Pass presentation and verify it first."""

from ..catalog.labels import LABELS
from ..catalog.model import Product
from ..demo.seed import STOCKOUT_ID, stockout_note
from ..orders.supply import LineRequest
from ..policy.mandate import AUDIENCE, MandateError
from ..text.format import short_ref
from ..trust.claims import claim_check
from .schemas import (
    ConfirmIn,
    NonceView,
    OrderView,
    ProductSummary,
    SimulatedMark,
    SupplyRequestIn,
    SupplyRequestView,
)
from .state import Ctx

MAX_SEARCH = 20


def bearer(header: str | None) -> str:
    """`Authorization: SD-JWT <presentation>` (Bearer is accepted too)."""
    if not header:
        raise MandateError("no Spend Pass in the Authorization header")
    scheme, _, token = header.strip().partition(" ")
    if scheme.lower() not in ("sd-jwt", "bearer") or not token.strip():
        raise MandateError("Authorization must be 'SD-JWT <presentation>'")
    return token.strip()


def product_summary(p: Product) -> ProductSummary:
    text = p.planted_en or p.marketing_en
    return ProductSummary(
        id=p.id, name=p.name_en, category=p.category, sales_unit=p.sales_unit,
        claims=[{"claim": c, "grade": str((g := claim_check(p, c))[0]), "note": "; ".join(g[1])}
                for c in sorted(p.claims)],
        allergens_contains=sorted(p.contains),
        labels=[LABELS[c].name if c in LABELS else c for c in sorted(p.labels)],
        description_untrusted={"text": text, "planted": bool(p.planted_en)} if text else None,
    )


def search_products(ctx: Ctx, text: str | None = None, category: str | None = None,
                    claims: list[str] | None = None, limit: int = 10) -> list[ProductSummary]:
    """Static catalog only, never a live call."""
    limit = max(1, min(int(limit), MAX_SEARCH))
    return [product_summary(p) for p in ctx.catalog.search(text=text, category_prefix=category,
                                                           claims=set(claims or ()), limit=limit)]


def nonce(ctx: Ctx) -> NonceView:
    now = ctx.now()
    return NonceView(nonce=ctx.nonces.issue(now), aud=AUDIENCE, iat=int(now.timestamp()))


def _name(ctx: Ctx, pid: str) -> str:
    p = ctx.catalog.get(pid)
    return short_ref(p.name_en) if p else pid


def _request_view(ctx: Ctx, req: dict) -> SupplyRequestView:
    view = SupplyRequestView.model_validate(req)
    if ctx.stockout() and any(ln.need.product_id == STOCKOUT_ID for ln in view.lines):
        view.simulated = [SimulatedMark(what=f"stock-out of {_name(ctx, STOCKOUT_ID)}", sentence=stockout_note(ctx.real_stock()))]
    return view


def request_supply(ctx: Ctx, spend_pass: str, body: SupplyRequestIn) -> SupplyRequestView:
    mandate = ctx.verify(spend_pass)
    req = ctx.supply.request_supply(
        mandate=mandate, deliver_by=body.deliver_by, idempotency_key=body.idempotency_key, agent=mandate.holder,
        lines=[LineRequest(ln.text, ln.product_id, ln.quantity, ln.unit) for ln in body.lines])
    return _request_view(ctx, req)


def get_request(ctx: Ctx, request_id: str) -> SupplyRequestView:
    return _request_view(ctx, ctx.supply.get_request(request_id))


def confirm_order(ctx: Ctx, spend_pass: str, body: ConfirmIn) -> OrderView:
    mandate = ctx.verify(spend_pass)
    o = ctx.supply.confirm_order(mandate=mandate, request_id=body.request_id, agent=mandate.holder,
                                 choice=[(c.product_id, c.sales_qty) for c in body.choice],
                                 idempotency_key=body.idempotency_key)
    return OrderView.model_validate(o)


def get_order(ctx: Ctx, order_id: str) -> OrderView:
    return OrderView.model_validate(ctx.orders.get(order_id))
