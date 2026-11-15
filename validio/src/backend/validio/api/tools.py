"""The five agent tools as plain functions. The HTTP routes under /agent/v1 and the MCP server both
call these, so there is one code path. Writes take the Spend Pass presentation and verify it first."""

import threading

from ..catalog.labels import LABELS
from ..catalog.model import Product
from ..demo.seed import STOCKOUT_ID, stockout_note
from ..matching.need import search_catalog
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
    """Static catalog only, never a live call. Words in a kitchen's terms find Valio's ("stock" finds bouillon);
    with VALIDIO_SEMANTIC=1 the local semantic search adds products by meaning (matching/semantic.py)."""
    limit = max(1, min(int(limit), MAX_SEARCH))
    return [product_summary(p) for p in search_catalog(ctx.catalog, text, category, set(claims or ()), limit)]


def nonce(ctx: Ctx) -> NonceView:
    now = ctx.now()
    return NonceView(nonce=ctx.nonces.issue(now), aud=AUDIENCE, iat=int(now.timestamp()))


def _name(ctx: Ctx, pid: str) -> str:
    p = ctx.catalog.get(pid)
    return short_ref(p.name_en) if p else pid


def _request_view(ctx: Ctx, req: dict) -> SupplyRequestView:
    view = SupplyRequestView.model_validate(req)
    view.used_before_cents = ctx.orders.used_before(view.spend_pass_id, view.created_at, view.order_id)
    if ctx.stockout() and any(ln.need.product_id == STOCKOUT_ID for ln in view.lines):
        view.simulated = [SimulatedMark(what=f"stock-out of {_name(ctx, STOCKOUT_ID)}", sentence=stockout_note(ctx.real_stock()))]
    return view


def request_supply(ctx: Ctx, spend_pass: str, body: SupplyRequestIn) -> SupplyRequestView:
    mandate = ctx.verify(spend_pass)
    req = ctx.supply.request_supply(
        mandate=mandate, deliver_by=body.deliver_by, idempotency_key=body.idempotency_key, agent=mandate.holder,
        lines=[LineRequest(ln.text, ln.product_id, ln.quantity, ln.unit) for ln in body.lines])
    return _request_view(ctx, req)


# Built views by (store file, store serial, request id), each with the store's change count it was built at. The
# inbox, Activity and the ledger are polled every two seconds and build a view per request, so a view is built
# again only after a write to the kitchen's store (or a demo switch). The serial is never reused in the process
# (unlike id(), which a new store may get once an evicted account's runtime is gone), so one kitchen never gets
# another's view; a reset opens a new store and also drops the file's views (forget_views). Callers get a deep
# copy: some of them trim the lists.
_VIEWS: dict[tuple[str, int, str], tuple[int, SupplyRequestView]] = {}
_VIEWS_MAX = 5000
_VIEWS_LOCK = threading.Lock()


def _generation(store) -> int:
    """Rows changed through the kitchen's one connection: every write, the ledger and the demo switches (each
    switch writes a ledger entry) count."""
    return store.con.total_changes


def forget_views(db_path) -> None:
    """Every built view of this store file, called on a reset."""
    path = str(db_path)
    with _VIEWS_LOCK:
        for k in [k for k in _VIEWS if k[0] == path]:
            del _VIEWS[k]


def _copy(v: SupplyRequestView) -> SupplyRequestView:
    """A copy whose own fields and option lists a caller may change (ui.asked_apart trims the lists); the
    options themselves are shared and never changed in place."""
    lines = [ln.model_copy(update={"options": list(ln.options),
                                   "substitutes": None if ln.substitutes is None else list(ln.substitutes),
                                   "beyond_list": None if ln.beyond_list is None else list(ln.beyond_list)})
             for ln in v.lines]
    return v.model_copy(update={"lines": lines})


def get_request(ctx: Ctx, request_id: str) -> SupplyRequestView:
    store = ctx.store
    key, gen = (str(store.path), store.serial, request_id), _generation(store)
    with _VIEWS_LOCK:
        hit = _VIEWS.get(key)
    if hit is not None and hit[0] == gen:
        return _copy(hit[1])
    view = _request_view(ctx, ctx.supply.get_request(request_id))
    with _VIEWS_LOCK:
        if len(_VIEWS) >= _VIEWS_MAX:
            _VIEWS.clear()
        _VIEWS[key] = (gen, _copy(view))
    return view


def confirm_order(ctx: Ctx, spend_pass: str, body: ConfirmIn) -> OrderView:
    mandate = ctx.verify(spend_pass)
    o = ctx.supply.confirm_order(mandate=mandate, request_id=body.request_id, agent=mandate.holder,
                                 choice=[(c.product_id, c.sales_qty) for c in body.choice],
                                 idempotency_key=body.idempotency_key)
    return OrderView.model_validate(o)


def get_order(ctx: Ctx, order_id: str) -> OrderView:
    from ..matching.need import CLAIM_NAMES
    from ..orders.explain import explain
    from ..orders.supply import order_status

    o = ctx.orders.get(order_id)
    diet = [CLAIM_NAMES.get(c, c) for c in o.get("requiredClaims") or (o.get("mandate") or {}).get("diet") or ()]
    o = {**o, "decision": {**o["decision"], **explain(o["decision"], order_status(o), diet, o.get("deliverBy"))}}
    view = OrderView.model_validate(o)
    view.used_before_cents = ctx.orders.used_before(o["spendPassId"], o["history"][0]["at"], o["id"])
    return view
