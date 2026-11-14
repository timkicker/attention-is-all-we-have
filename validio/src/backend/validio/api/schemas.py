"""Typed shapes of the agent API and the web app API. JSON is camelCase, Python is snake_case.

The response shapes follow the web app's src/frontend/src/lib/api/types.ts. Inputs ignore unknown
fields, so an agent that sends its own price or trust level changes nothing."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel


class Model(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="ignore")


def _d():
    from . import display
    return display


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


class SessionIn(Model):
    token: str = Field(max_length=200)


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
    value_text: str | None = Field(None, description="the value in words: no placeholder count, codes or ratios")
    note_text: str | None = None

    @model_validator(mode="after")
    def _text(self):
        if self.value_text is None and self.note_text is None:
            v, n = _d().fact_text(self.field, self.value, self.note)
            self.value_text, self.note_text = v, n
        return self


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
    summary: str | None = Field(None, description="at most about 12 words for the screen, the sentence is the detail")

    @model_validator(mode="after")
    def _text(self):
        self.summary = self.summary or _d().summary(self.sentence)
        return self


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
    display_name: str | None = Field(None, description="short, at most about five words, the same as shortName")
    short_name: str | None = None
    full_name: str | None = Field(None, description="the whole product name, tidied, for a detail line")
    qty_text: str | None = None
    money_text: str | None = None
    reasons: list[str] | None = Field(None, description="the sentence as a list, one reason each")
    short_text: str | None = Field(None, description="at most about eight words: \"90.00 € more.\"")
    group_text: str | None = Field(None, description="turned-down options only: their heading, \"Order cut-off passed\"")
    group_order: int | None = Field(None, description="turned-down options only: the heading's place, lowest first")

    @model_validator(mode="after")
    def _text(self):
        d = _d()
        from ..text.format import display_name
        self.full_name = self.full_name or display_name(self.name)
        self.short_name = self.short_name or d.short_name(self.name)
        self.display_name = self.short_name
        self.qty_text = self.qty_text or d.qty(self.quantity, self.unit, self.product_id)
        if self.money_text is None and self.total_cents is not None:
            self.money_text = d.money(self.total_cents)
        self.reasons = self.reasons if self.reasons is not None else d.reasons(self.sentence)
        self.short_text = self.short_text or d.short_text(self.verdict, self.reasons)
        if self.verdict in d.TURNED_DOWN and self.group_text is None:
            self.group_text, self.group_order, _ = d.group(self.reasons)
        return self


class NeedView(Model):
    what: str
    quantity: float
    unit: str
    diet: list[str]
    deliver_by: str
    product_id: str | None = None
    qty_text: str | None = Field(None, description="in the product's sales unit for a product line: 200 bags")
    deliver_by_text: str | None = None

    @model_validator(mode="after")
    def _text(self):
        d = _d()
        self.qty_text = self.qty_text or d.qty(self.quantity, self.unit, self.product_id)
        self.deliver_by_text = self.deliver_by_text or d.day_word(self.deliver_by)
        return self


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

    @model_validator(mode="after")
    def _names(self):
        # two products that would read the same get their brand back
        opts = [*self.options, *(self.substitutes or []), *(self.beyond_list or [])]
        for o, n in zip(opts, _d().short_names([o.name for o in opts]), strict=True):
            o.short_name = o.display_name = n
        return self


class SimulatedMark(Model):
    what: str
    sentence: str


class AskedFor(Model):
    product_id: str
    display_name: str
    state_text: str


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
    title: str | None = Field(None, description="from the parsed need, never the agent's own words")
    agent_text: str | None = Field(None, description="what the agent sent, as it sent it")
    money_text: str | None = None
    time_text: str | None = None
    display_name: str | None = Field(None, description="the same as title, the name types.ts already reads")
    title_text: str | None = Field(None, description="the title without the date: \"200 bags of ...\"")
    asked_for: AskedFor | None = Field(None, description="the product the request named, kept out of the options")

    used_before_cents: int | None = Field(
        None, description="what orders placed under the same Spend Pass before this request add up to")

    @model_validator(mode="after")
    def _text(self):
        d = _d()
        self.agent_text = self.agent_text or self.text
        self.title = self.title or d.title(self.lines, self.deliver_by) or "Request"
        self.display_name = self.display_name or self.title
        self.title_text = self.title_text or d.title(self.lines, None)
        if self.money_text is None and self.total_cents is not None:
            self.money_text = d.money(self.total_cents)
        self.time_text = self.time_text or d.time_text(self.created_at)
        return self


class InboxItem(Model):
    id: str
    created_at: str
    text: str
    status: str
    sentence: str
    total_cents: int | None = None
    title: str | None = None
    title_text: str | None = None
    display_name: str | None = None
    summary: str | None = None
    money_text: str | None = None
    time_text: str | None = None

    @model_validator(mode="after")
    def _text(self):
        d = _d()
        self.display_name = self.display_name or self.title
        self.summary = self.summary or d.summary(self.sentence)
        if self.money_text is None and self.total_cents is not None:
            self.money_text = d.money(self.total_cents)
        self.time_text = self.time_text or d.time_text(self.created_at)
        return self


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
    display_name: str | None = Field(None, description="short, at most about five words, the same as shortName")
    short_name: str | None = None
    full_name: str | None = Field(None, description="the whole product name, tidied, for a detail line")
    qty_text: str | None = None
    money_text: str | None = None
    delivery_text: str | None = None

    @model_validator(mode="after")
    def _text(self):
        d = _d()
        from ..text.format import display_name
        self.full_name = self.full_name or display_name(self.name)
        self.short_name = self.short_name or d.short_name(self.name)
        self.display_name = self.short_name
        self.qty_text = self.qty_text or d.qty(self.quantity, self.unit, self.product_id)
        if self.money_text is None and self.total_cents is not None:
            self.money_text = d.money(self.total_cents)
        if self.delivery_text is None and self.delivery_date:
            self.delivery_text = f"delivery {d.day_word(self.delivery_date)}"
        return self


class HistoryStep(Model):
    state: str
    at: str
    time_text: str | None = None

    @model_validator(mode="after")
    def _text(self):
        self.time_text = self.time_text or _d().time_text(self.at)
        return self


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
    money_text: str | None = None
    used_before_cents: int | None = Field(
        None, description="what orders placed under the same Spend Pass before this one add up to")
    question_text: str | None = Field(None, description="the approve page's question, \"Order 10 × 2.5 kg of ... for 180.10 €?\"")

    @model_validator(mode="after")
    def _text(self):
        d = _d()
        self.money_text = self.money_text or d.money(self.total_cents)
        if self.question_text is None:
            from ..text.format import qty_of
            what = (qty_of(self.lines[0].quantity, d.product(self.lines[0].product_id), self.lines[0].unit,
                           self.lines[0].name) if len(self.lines) == 1 else f"these {len(self.lines)} lines")
            self.question_text = f"Order {what} for {self.money_text}?"
        return self


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
    used_cents: int | None = Field(None, description="what placed orders under this Spend Pass add up to")
    disclosed: list[str]
    hidden: list[str]
    disclosed_text: list[str] | None = Field(None, description="the disclosed fields as a person reads them")
    hidden_text: list[str] | None = None

    @model_validator(mode="after")
    def _text(self):
        d = _d()
        self.disclosed_text = self.disclosed_text or d.pass_fields(self.disclosed)
        self.hidden_text = self.hidden_text or d.pass_fields(self.hidden)
        return self


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
    request_id: str | None = Field(None, description="the request or Steady Order the entry belongs to: R-2, S-1")
    prev_hash: str
    hash: str
    actor_text: str | None = None
    time_text: str | None = None
    summary: str | None = None
    disclosed_text: list[str] | None = None
    display_text: str | None = Field(None, description="one short sentence with a verb, no actor, for the row")

    @model_validator(mode="after")
    def _text(self):
        d = _d()
        self.actor_text = self.actor_text or d.actor(self.actor)
        self.time_text = self.time_text or d.time_text(self.at)
        self.summary = self.summary or d.summary(self.sentence)
        self.disclosed_text = self.disclosed_text or d.pass_fields(self.disclosed)
        return self


class ChainStatus(Model):
    ok: bool
    count: int
    broken_at: int | None = None


class LedgerGroup(Model):
    request_id: str
    title_text: str


class LedgerView(Model):
    entries: list[LedgerEntryView]
    chain: ChainStatus
    groups: list[LedgerGroup] = Field([], description="one head per request or Steady Order, in ledger order")


class RealStock(Model):
    quantity: float
    unit: str


class LedgerHeadView(Model):
    """The Open Ledger head as the kitchen signed it. Valio can pin it and later check that the ledger it is
    shown still ends here or grew from here."""
    count: int
    hash: str
    at: str | None = None
    signature: str | None = None  # compact JWS, ES256, payload {"at","count","hash","typ"} as canonical JSON
    public_key: dict | None = None  # the kitchen's public JWK, the same key that signs the Spend Pass
    signature_ok: bool


class DemoState(Model):
    code_required: bool = Field(True, description="false when no approve code is configured")
    stock_out_466375: bool = Field(alias="stockOut466375")
    real_stock_466375: RealStock | None = Field(
        None, alias="realStock466375", description="what Valio really has of 466375, read at request time")


class NonceView(Model):
    nonce: str
    aud: str
    iat: int  # Validio's clock in Unix seconds: sign the key binding JWT with this as its iat


class Health(Model):
    status: str
