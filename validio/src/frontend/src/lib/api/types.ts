// Hand-written types for the Validio web API, taken from the blueprint's
// "Data model" and "MCP tools" sections. They stand in until `make types`
// generates schema.d.ts from the backend's OpenAPI file; then these become
// aliases of the generated ones and the pages stay as they are.
//
// Money is always whole cents. Dates are ISO 8601 strings.

/** How far a single fact can be trusted. */
export type FactGrade =
  | "attested"
  | "attested_until"
  | "consistent"
  | "contradicted"
  | "unchecked"
  | "unknown"
  | "untrusted"
  | "missing";

export interface Fact {
  field: string;
  /** Absent when Valio or the catalog has no value (grade "missing" or "unknown"). */
  value?: string | number | boolean | null;
  grade: FactGrade;
  /** Where the value comes from, e.g. "valio:availability", "catalog:claims". */
  source: string;
  note?: string;
  /** Set for attested_until, e.g. the end of a contract price. */
  until?: string;
  /** The value in words: "100 % of orders", "milk and lactose", "Valio gives no real count". */
  valueText?: string;
  noteText?: string;
}

/** Text written by a supplier. Shown, never used for a decision. */
export interface SupplierText {
  text: string;
  grade: "untrusted";
  /** True when the team planted this line for the demo. */
  planted?: boolean;
  /** What the reader made of it. It never changes a decision. */
  reader?: Reader;
}

/** What a model read in a supplier text. Shown, never used for a decision. */
export interface Reader {
  flags: { code: "addresses_agents" | "gives_instruction" | "mentions_claim"; text: string }[];
  summary: string;
}

export interface Product {
  id: string;
  name: string;
  unit: string;
  facts: Fact[];
  labels: string[];
  supplierText?: SupplierText;
}

/** What the rule engine said. */
export type Outcome = "auto_order" | "ask_human" | "block";

export type RequestStatus =
  | "working"
  | "ordered_alone"
  | "waiting"
  | "approved"
  | "ordered"
  | "rejected"
  | "blocked";

export type OptionVerdict =
  | "chosen"
  | "ranked"
  | "rejected"
  | "blocked"
  | "not_deliverable";

export interface RankedOption {
  productId: string;
  name: string;
  /** 1 is best. Rejected options carry no rank. */
  rank?: number;
  verdict: OptionVerdict;
  quantity?: number;
  unit?: string;
  totalCents?: number;
  /** One sentence a chef understands. */
  sentence: string;
  facts: Fact[];
  /** True when the option comes from Valio's own substitute list. */
  onValioList?: boolean;
  /** True when the option replaces the product the request named. */
  isSubstitute?: boolean;
  supplierText?: SupplierText;
  /** At most about eight words: "+90.00 €", "Cheapest, always delivered in full.", "Cheapest lactose-free swap." */
  shortText?: string;
  /** Turned-down options only (rejected, blocked, not_deliverable): "Order cut-off passed", "Not lactose free". */
  groupText?: string;
  /** Turned-down options only: the heading's place, lowest first. The same heading has the same number. */
  groupOrder?: number;
  /** The reasons for the Why fold, without the one shortText already says. */
  whyReasons?: string[];
  /** The facts Validio confirmed, one short fact each: "Price 1.01 €", "Free from lactose". */
  checks?: string[];
  /** At most about five words: "Lactose-free mozzarella 125 g". Brand only when two would read the same. */
  displayName?: string;
  /** The same as displayName. */
  shortName?: string;
  /** The whole catalogue name without ® and shouting, sizes as "2.5 kg", for a detail line. */
  fullName?: string;
  /** "10 × 2.5 kg", "200 bags", in the catalogue's sales unit. */
  qtyText?: string;
  /** "1,010.00 €" */
  moneyText?: string;
  /** The sentence as a list, one reason each; the screen joins them. */
  reasons?: string[];
  /** Price per litre or kilo when the pack size is known: "1.01 € per l". */
  unitPriceText?: string;
  /** Valio's earliest delivery date, ISO. */
  deliveryDate?: string;
  /** "Arrives Mon 16 Nov". */
  deliveryText?: string;
  /** "Order by Sun 15 Nov 17:00", or "Order cut-off passed Thu 12 Nov 15:00". */
  cutoffText?: string;
  /** "Delivered in full 99 of 100 times", "No record yet: treated as least reliable". */
  reliabilityText?: string;
  /** The diet the request needs with how sure: "Lactose free: Valio confirms, ingredients agree". */
  dietText?: string;
  /** Chosen option only: why it won, two short sentences. */
  whyText?: string;
  /** Every other option: why not this one. "Costs 90.00 € more: 1.10 € per l against 1.01 €." */
  whyNotText?: string;
}

export interface SplitPart {
  productId: string;
  name: string;
  quantity: number;
  unit: string;
  totalCents: number;
  onValioList: boolean;
  /** At most about five words, the same as shortName. */
  displayName?: string;
  shortName?: string;
  fullName?: string;
  qtyText?: string;
  moneyText?: string;
}

export interface Split {
  parts: SplitPart[];
  totalCents: number;
  extraCostCents: number;
  extraCostPct: number;
}

/** The typed need Validio read from the request text. */
export interface Need {
  /** Set when the request named a product id instead of text. */
  productId?: string;
  what: string;
  quantity: number;
  unit: string;
  diet: string[];
  deliverBy: string;
  /** "1,000 litres", or "200 bags" in the product's sales unit for a product line. */
  qtyText?: string;
  /** "Mon 16 Nov" */
  deliverByText?: string;
}

export interface Decision {
  outcome: Outcome;
  ruleIds: string[];
  /** The full sentence, for the ledger and a details view. */
  sentence: string;
  /** At most about 12 words for the screen. */
  summary?: string;
  /** Why it ended here, for every status. */
  reasonCode?: ReasonCode;
  /** One plain sentence in the kitchen's own limits: "Bought without asking: 1,010.00 € is under your 1,200.00 € limit for buying alone." */
  ownerText?: string;
}

export type ReasonCode =
  | "auto_ok"
  | "over_alone"
  | "over_budget"
  | "swap_unlisted"
  | "diet_unchecked"
  | "stock_unconfirmed"
  | "ask_other"
  | "week_cap"
  | "hard_cap"
  | "diet"
  | "no_price"
  | "sales_block"
  | "outside_groups"
  | "none_available"
  | "blocked_other"
  | "valio_down"
  | "too_many"
  | "unreadable";

export interface RequestLine {
  lineId: string;
  text: string;
  need: Need;
  options: RankedOption[];
  /** Valio's listed substitutes and their verdicts, when a swap was needed. */
  substitutes?: RankedOption[];
  /** Options found in the catalog beyond Valio's list. */
  beyondList?: RankedOption[];
  split?: Split;
  /** Footnote that applies to the whole line, e.g. the carbon note. */
  note?: string;
  /** What Validio proposes for this line; the agent confirms it with confirm_order. */
  chosen?: Choice;
  /** One sentence on why a swap was needed and what it found. */
  swapSentence?: string;
  /** The Best Pick key that chose between the top two: "price", "delivery record", "labels", "footprint", "only option". */
  decidedBy?: string;
  /** "Decided by: price." or "Only one option fits." */
  decidedByText?: string;
}

export interface Choice {
  productId: string;
  salesQty: number;
  isSubstitute: boolean;
  onValioList: boolean;
}

/** Something on screen that is not real, said out loud. */
export interface SimulatedMark {
  what: string;
  sentence: string;
}

export interface LiveChecked {
  calls: number;
  ids: number;
  idsPerCall: number[];
}

/** `request_supply` / `get_request` result. */
export interface SupplyRequest {
  id: string;
  /** The same as id; the agent tools read this name. */
  requestId?: string;
  createdAt: string;
  agent: string;
  text: string;
  /** The kitchen's ask in display words, when the backend writes one. */
  displayName?: string;
  deliverBy: string;
  status: RequestStatus;
  spendPassId: string;
  lines: RequestLine[];
  decision: Decision;
  totalCents?: number;
  /** What was asked live at Valio: calls, distinct product ids, ids per call (at most 40). */
  liveChecked: LiveChecked;
  orderId?: string;
  /** For waiting requests: the one question for the owner. */
  question?: string;
  simulated?: SimulatedMark[];
  /** From the parsed need, never the agent's words: "1,000 litres of lactose-free milk by Mon 16 Nov". */
  title?: string;
  /** What the agent sent, as it sent it. */
  agentText?: string;
  moneyText?: string;
  /** "10:00" on the demo clock. */
  timeText?: string;
  /** What orders placed under the same Spend Pass before this request add up to: R-2 gives 101000. */
  usedBeforeCents?: number;
  /** The title without the date: "200 bags of lactose-free mozzarella 125 g". */
  titleText?: string;
  /** The product the request named, when Validio turned it down. It is then not among the options. */
  askedFor?: { productId: string; displayName: string; stateText: string };
  /** When Validio read Valio live for this request: "10:14". */
  liveAt?: string;
  /** The asked-for product's live count, for the chosen row's fold: "Valio's live count of ...: 11,603 bags." */
  liveCountText?: string;
  /** The one muted line that names a simulated stock-out: "Out of stock (simulated). Swap not on Valio's list." */
  leadText?: string;
  /** How long Validio took for this request, Valio included. */
  elapsedMs?: number;
  /** How Valio was asked; replay means recorded answers, never "Live". */
  valioMode?: ValioMode;
  /** "Done in 3 s, 12 products checked with Valio". */
  speedText?: string;
  /** "Valio checked 10:00", or "Valio's recorded answers" in replay. */
  valioText?: string;
}

export type ValioMode = "live" | "record" | "replay";

/** One row in the inbox. */
export interface InboxItem {
  id: string;
  createdAt: string;
  text: string;
  /** The kitchen's ask in display words, when the backend writes one. */
  displayName?: string;
  status: RequestStatus;
  sentence: string;
  totalCents?: number;
  /** As on the request. */
  title?: string;
  /** At most about 12 words of `sentence`. */
  summary?: string;
  moneyText?: string;
  timeText?: string;
  /** The title without the date. */
  titleText?: string;
}

export type OrderState = "waiting" | "approved" | "placed" | "rejected" | "blocked";

export interface OrderLine {
  productId: string;
  name: string;
  quantity: number;
  unit: string;
  /** Valio's price per unit, asked again at order time. */
  priceCents: number;
  totalCents: number;
  /** End of the contract price, when Valio gives one. */
  priceValidTo?: string;
  /** The day Valio says it can deliver. */
  deliveryDate?: string;
  /** False when Valio cannot deliver this line by the date asked. */
  deliverable: boolean;
  isSubstitute: boolean;
  onValioList: boolean;
  facts: Fact[];
  /** At most about five words: "Lactose-free mozzarella 125 g". Brand only when two would read the same. */
  displayName?: string;
  /** The same as displayName. */
  shortName?: string;
  /** The whole catalogue name without ® and shouting, sizes as "2.5 kg", for a detail line. */
  fullName?: string;
  qtyText?: string;
  moneyText?: string;
  /** "delivery Mon 16 Nov" */
  deliveryText?: string;
}

/** `confirm_order` / `get_order` result. */
export interface Order {
  id: string;
  requestId: string;
  state: OrderState;
  lines: OrderLine[];
  totalCents: number;
  /** Every state the order went through, oldest first. */
  history: { state: OrderState; at: string; timeText?: string }[];
  decision: Decision;
  spendPassId: string;
  deliverBy: string;
  /** The role that approved, e.g. "owner". Never a name. */
  approvedBy?: string;
  moneyText?: string;
  /** The approve page's question: "Order 10 × 2.5 kg of mozzarella-fontal crumbled cheese for 180.10 €?" */
  questionText?: string;
  /** What orders placed under the same Spend Pass before this one add up to. */
  usedBeforeCents?: number;
}

/**
 * The Spend Pass as the web app sees it. Fields the agent did not disclose are
 * absent, and `hidden` names them so the page can say they exist.
 */
export interface SpendPass {
  id: string;
  issuer: string;
  holder: string;
  validFrom: string;
  validTo: string;
  autoLimitCents?: number;
  hardCapCents?: number;
  /** The Rules' per week limit, for all orders under the pass together. */
  weekCapCents?: number;
  diet?: string[];
  categories: string[];
  deliverBy: string;
  substitutes: string;
  split: { maxExtraCostPct: number; allowListedSubstitutes: boolean };
  disclosed: string[];
  hidden: string[];
  /** The same fields as a person reads them: "auto limit", "never above", "diet". */
  disclosedText?: string[];
  hiddenText?: string[];
  /** One sentence: "The agent sees your limits and diet rules, not who approves or your preferred labels." */
  seesText?: string;
  /** What placed orders under this Spend Pass add up to. */
  usedCents?: number;
}

export type LedgerKind =
  | "request"
  | "decision"
  | "order"
  | "approval"
  | "simulation"
  | "renewal"
  | "spend_pass"
  | "agent";

export interface LedgerEntry {
  seq: number;
  at: string;
  actor: string;
  kind: LedgerKind;
  sentence: string;
  facts: Fact[];
  spendPassId?: string;
  /** Spend Pass fields that were shown for this decision. */
  disclosed: string[];
  ruleIds: string[];
  orderId?: string;
  prevHash: string;
  hash: string;
  /** "Validio", "You", "Agent", "Demo" */
  actorText?: string;
  /** "10:04" on the demo clock. */
  timeText?: string;
  /** At most about 12 words of `sentence`. */
  summary?: string;
  /** `disclosed` as a person reads it. */
  disclosedText?: string[];
  /** The request or Steady Order the entry belongs to: "R-1", "R-2", "S-1". A simulation takes the request it was made for. */
  requestId?: string;
  /** One short sentence with a verb for the row: no actor, money as "1,200.00 €", an order id once. */
  displayText?: string;
}

export interface ChainStatus {
  ok: boolean;
  count: number;
  /** The first entry whose hash does not match, when the chain is broken. */
  brokenAt?: number;
}

export interface Ledger {
  entries: LedgerEntry[];
  chain: ChainStatus;
  /** One head per request or Steady Order, in ledger order. */
  groups?: { requestId: string; titleText: string }[];
}

export type DriftKind = "per_guest_up" | "cost_up" | "contract_ends" | "stock_below";

export interface DriftFlag {
  kind: DriftKind;
  sentence: string;
  pct?: number;
}

export type SteadyLineResult =
  | "pending"
  | "renewed"
  | "split_renewed"
  | "waiting"
  | "flagged"
  | "accepted"
  /** Nothing can be ordered: a rule blocks it, or Valio has none (then no acceptLabel). */
  | "blocked";

export interface SteadyLine {
  productId: string;
  name: string;
  unit: string;
  usualQuantity: number;
  thisWeekQuantity?: number;
  totalCents?: number;
  result: SteadyLineResult;
  sentence: string;
  flags: DriftFlag[];
  split?: Split;
  /** Label of the button that lets the line through, e.g. "Order 27 now". */
  acceptLabel?: string;
  /** Amount per week, oldest first, for the lines that drift. */
  history?: number[];
  /** The order this line was placed in, once it was. */
  orderId?: string;
  /** The rules that decided the line. */
  ruleIds?: string[];
  /** At most about five words, the same as shortName. */
  displayName?: string;
  shortName?: string;
  fullName?: string;
  /** "200 × 200 g", "98 bags" */
  usualQtyText?: string;
  qtyText?: string;
  moneyText?: string;
  /** A held line in a few words: "None in stock at Valio.", "27 of 30 in stock." */
  shortText?: string;
}

export interface SteadyOrder {
  id: string;
  name: string;
  weekday: string;
  guestsPerWeek: number;
  weeksLearned: number;
  /** The history behind this order is invented for the demo. */
  simulatedHistory: boolean;
  renewedAt?: string;
  lines: SteadyLine[];
  /** The Steady Orders' own weekly Spend Pass; its limits hold across the orders placed under it. */
  steadyPass?: SteadyPass;
  /** One state for the whole order, so no line repeats it. */
  state?: "renewed" | "not_renewed";
  /** "Not renewed this week", "Renewed Sat 14 Nov, 10:12" */
  stateText?: string;
}

export interface SteadyPass {
  id: string;
  /** ISO 8601, Monday 00:00 of the week. */
  validFrom: string;
  /** ISO 8601, the next Monday 00:00. */
  validTo: string;
  autoLimitCents?: number;
  hardCapCents?: number;
  /** What the placed orders under this pass add up to. */
  usedCents: number;
}

export interface SteadyOrderSummary {
  id: string;
  name: string;
  weekday: string;
  lineCount: number;
  flagCount: number;
  renewedAt?: string;
  state?: "renewed" | "not_renewed";
  stateText?: string;
}

/** The few demo switches the presenter presses. Each one is simulated. */
/** POST /api/spend-pass: the owner signs M-1 again (approval code as for approve). Answers the SpendPassView.
 *  422 when alone is above never above, 403 on a wrong code. Valio answers are recorded only for lactose free
 *  and 16 Nov, so other values make the next request a clean 503. Start over restores the seeded pass. */
export interface SpendPassIn {
  autoLimitCents: number;
  hardCapCents: number;
  diet: ('FREE_FROM_LACTOSE' | 'FREE_FROM_GLUTEN' | 'VEGAN')[];
  /** ISO date. */
  deliverBy: string;
  /** false: no substitute orders alone. */
  substitutes: boolean;
  code?: string;
}

export interface DemoState {
  /** False when no approve code is configured: approve needs no code then. */
  codeRequired?: boolean;
  stockOut466375: boolean;
  /** The demo switch "Valio not answering": every Valio read fails (POST /api/demo/valio-down). */
  valioDown?: boolean;
  valioMode?: ValioMode;
  /** "Valio's recorded answers" or "Valio live". */
  valioModeText?: string;
  /** What Valio really has of 466375, read from its availability answer at request time. */
  realStock466375?: { quantity: number; unit: string };
}

/** The body of a 409 from approve or reject. */
export interface ConflictBody {
  detail: string;
  /** refused: Valio was asked again and nothing was ordered. already: decided before. conflict: idempotency key reused. */
  code?: "refused" | "already" | "conflict";
  /** code refused only: "Valio's price went from 18.01 € to 18.60 € (+3.3 %). Not ordered." */
  refusedText?: string;
}

// ---------- accounts (validio/docs/ACCOUNTS-API.md) ----------

/** The kitchen's account: one per kitchen, the session cookie names it. */
export interface Account {
  id: string;
  name: string;
  /** Null for a demo copy. */
  email: string | null;
  /** The kitchen's Valio Aimo customer number, typed once at sign up. */
  customerNumber: string;
  deliveryAddress: string;
  /** A copy of the demo kitchen, one per browser session. */
  isDemo: boolean;
  /** Only on a demo copy: its fixed approval code, shown in the demo bar on purpose. */
  demoCode?: string;
  /** The Inbox checklist. */
  setup: { kitchen: boolean; rules: boolean; agent: boolean; done: boolean };
  agent: AgentState;
  createdAt: string;
}

export interface AgentState {
  state: "none" | "pairing" | "consent" | "active" | "paused";
  pairing?: { code: string; expiresAt: string; mcpUrl: string; apiUrl: string };
  /** verifyCode: "XXX-XXX", the same code the MCP agent gets in its tool answer. */
  consent?: { name: string; keyId: string; may: string[]; verifyCode: string };
  agent?: { name: string; kind: "agent" | "mcp"; keyId: string; connectedAt: string; lastUsedAt: string | null; passId: string; passVersion: number };
  /** Newest first. */
  versions: { version: number; at: string; why: string }[];
}

export interface Rules {
  aloneUpToCents: number;
  approvalUpToCents: number;
  substitutes: "off" | "listed" | "extra";
  maxExtraPct: number;
  /** All orders under the pass together, blocked over it; null: no weekly limit. */
  perWeekCents: number | null;
  /** False until saved once: everything needs approval. */
  saved: boolean;
  passVersion: number;
}

export type RulesIn = Omit<Rules, "saved" | "passVersion"> & { code: string };

export type Diet = "FREE_FROM_LACTOSE" | "FREE_FROM_GLUTEN" | "VEGAN";

export interface Settings {
  kitchen: { name: string; customerNumber: string; deliveryAddress: string };
  diet: Diet[];
  login: { email: string | null };
}

export interface LoginIn {
  email: string;
  password: string;
}

export interface SignupIn extends LoginIn {
  name: string;
  customerNumber: string;
  /** The 6-digit approval code the owner sets now and types for every approval. */
  approvalCode: string;
}
