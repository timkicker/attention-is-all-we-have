"""Typed shapes of the agent API and the web app API. JSON is camelCase, Python is snake_case.

The response shapes follow the web app's src/frontend/src/lib/api/types.ts. Inputs ignore unknown
fields, so an agent that sends its own price or trust level changes nothing."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class Model(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="ignore")


# agent input


class SupplyLineIn(Model):
    text: str | None = Field(None, max_length=300, description="free text, e.g. '1000 litres of lactose-free milk'")
    product_id: str | None = Field(None, max_length=20)
    quantity: float | None = Field(None, gt=0, le=1_000_000)
    unit: str | None = Field(None, max_length=8, description="the product's sales unit, or L / KG")


class SupplyRequestIn(Model):
    lines: list[SupplyLineIn] = Field(min_length=1, max_length=10)
    deliver_by: date | None = None
    idempotency_key: str = Field(min_length=1, max_length=100)


class ChoiceIn(Model):
    product_id: str = Field(max_length=20)
    sales_qty: int = Field(gt=0, le=1_000_000)


class ConfirmIn(Model):
    request_id: str = Field(max_length=20)
    choice: list[ChoiceIn] = Field(min_length=1, max_length=10)
    idempotency_key: str = Field(min_length=1, max_length=100)


class ApproveIn(Model):
    code: str | None = Field(None, description="the 6 digit approval code, or the X-Approve-Code header")


# shared pieces


Grade = Literal["attested", "attested_until", "consistent", "contradicted", "unchecked", "unknown",
                "untrusted", "missing"]


class FactView(Model):
    field: str
    value: str | float | bool | None = None
    grade: Grade
    source: str
    note: str | None = None
    until: str | None = None


class ReaderFlagView(Model):
    code: Literal["addresses_agents", "gives_instruction", "mentions_claim"]
    text: str


class ReaderView(Model):
    """The reader's fixed shape (validio.reader.ReaderResult). Shown next to the text, never used to decide."""
    flags: list[ReaderFlagView]
    summary: str


class SupplierTextView(Model):
    text: str
    grade: Literal["untrusted"] = "untrusted"
    planted: bool | None = None
    reader: ReaderView | None = None


class DecisionView(Model):
    outcome: Literal["auto_order", "ask_human", "block"]
    rule_ids: list[str]
    sentence: str


# products


class ClaimView(Model):
    claim: str
    grade: Grade
    note: str | None = None


class ProductSummary(Model):
    id: str
    name: str
    category: str
    sales_unit: str
    claims: list[ClaimView]
    allergens_contains: list[str]
    labels: list[str]
    description_untrusted: SupplierTextView | None = None


# requests


class RankedOptionView(Model):
    product_id: str
    name: str
    rank: int | None = None
    verdict: Literal["chosen", "ranked", "rejected", "blocked", "not_deliverable"]
    quantity: int | None = None
    unit: str | None = None
    total_cents: int | None = None
    sentence: str
    facts: list[FactView]
    on_valio_list: bool | None = None
    is_substitute: bool | None = None
    supplier_text: SupplierTextView | None = None


class NeedView(Model):
    what: str
    quantity: float
    unit: str
    diet: list[str]
    deliver_by: str
    product_id: str | None = None


class ChoiceView(Model):
    product_id: str
    sales_qty: int
    is_substitute: bool = False
    on_valio_list: bool = False


class LiveChecked(Model):
    calls: int
    ids: int = Field(description="how many product ids were asked live at Valio for this request, at most 40")
    ids_per_call: list[int]


class RequestLineView(Model):
    line_id: str
    text: str
    need: NeedView
    options: list[RankedOptionView]
    substitutes: list[RankedOptionView] | None = None
    beyond_list: list[RankedOptionView] | None = None
    swap_sentence: str | None = None
    chosen: ChoiceView | None = Field(None, description="what Validio would order for this line")
    note: str | None = None


class SimulatedMark(Model):
    what: str
    sentence: str


class SupplyRequestView(Model):
    id: str
    request_id: str
    created_at: str
    agent: str
    text: str
    deliver_by: str | None = None
    status: Literal["working", "ordered_alone", "waiting", "approved", "ordered", "rejected", "blocked"]
    spend_pass_id: str
    lines: list[RequestLineView] = []
    decision: DecisionView | None = None
    total_cents: int | None = None
    live_checked: LiveChecked | None = None
    order_id: str | None = None
    question: str | None = None
    simulated: list[SimulatedMark] | None = None


class InboxItem(Model):
    id: str
    created_at: str
    text: str
    status: str
    sentence: str
    total_cents: int | None = None


# orders


class OrderLineView(Model):
    product_id: str
    name: str
    quantity: int
    unit: str
    price_cents: int | None = None
    total_cents: int | None = None
    price_valid_to: str | None = None
    delivery_date: str | None = None
    deliverable: bool
    is_substitute: bool = False
    on_valio_list: bool = False
    facts: list[FactView] = []


class HistoryStep(Model):
    state: str
    at: str


class OrderView(Model):
    id: str
    request_id: str | None = None
    state: Literal["waiting", "approved", "placed", "rejected", "blocked"]
    lines: list[OrderLineView]
    total_cents: int
    history: list[HistoryStep]
    decision: DecisionView
    spend_pass_id: str
    deliver_by: str
    approved_by: str | None = None


# Spend Pass, ledger, demo


class SplitView(Model):
    max_extra_cost_pct: float
    allow_listed_substitutes: bool


class SpendPassView(Model):
    id: str
    issuer: str
    holder: str
    valid_from: str
    valid_to: str
    auto_limit_cents: int | None = None
    hard_cap_cents: int | None = None
    diet: list[str] | None = None
    categories: list[str]
    deliver_by: str | None = None
    substitutes: str | None = None
    split: SplitView
    disclosed: list[str]
    hidden: list[str]


class LedgerEntryView(Model):
    seq: int
    at: str
    actor: str
    kind: str
    sentence: str
    facts: list[dict]
    spend_pass_id: str | None = None
    disclosed: list[str]
    rule_ids: list[str]
    order_id: str | None = None
    prev_hash: str
    hash: str


class ChainStatus(Model):
    ok: bool
    count: int
    broken_at: int | None = None


class LedgerView(Model):
    entries: list[LedgerEntryView]
    chain: ChainStatus


class DemoState(Model):
    stock_out_466375: bool = Field(alias="stockOut466375")


class NonceView(Model):
    nonce: str
    aud: str
    iat: int  # Validio's clock in Unix seconds: sign the key binding JWT with this as its iat


class Health(Model):
    status: str
