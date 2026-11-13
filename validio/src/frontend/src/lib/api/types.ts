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
  | "untrusted";

export interface Fact {
  field: string;
  value: string | number | boolean | null;
  grade: FactGrade;
  /** Where the value comes from, e.g. "valio:availability", "catalog:claims". */
  source: string;
  note?: string;
  /** Set for attested_until, e.g. the end of a contract price. */
  until?: string;
}

/** Text written by a supplier. Shown, never used for a decision. */
export interface SupplierText {
  text: string;
  grade: "untrusted";
  /** True when the team planted this line for the demo. */
  planted?: boolean;
  /** What the reader made of it. It never changes a decision. */
  reader?: { mentionsClaims: string[]; addressesAgents: boolean; note: string };
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
  supplierText?: SupplierText;
}

export interface SplitPart {
  productId: string;
  name: string;
  quantity: number;
  unit: string;
  totalCents: number;
  onValioList: boolean;
}

export interface Split {
  parts: SplitPart[];
  totalCents: number;
  extraCostCents: number;
  extraCostPct: number;
}

/** The typed need Validio read from the request text. */
export interface Need {
  what: string;
  quantity: number;
  unit: string;
  diet: string[];
  deliverBy: string;
}

export interface Decision {
  outcome: Outcome;
  ruleIds: string[];
  sentence: string;
}

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
}

/** Something on screen that is not real, said out loud. */
export interface SimulatedMark {
  what: string;
  sentence: string;
}

/** `request_supply` / `get_request` result. */
export interface SupplyRequest {
  id: string;
  createdAt: string;
  agent: string;
  text: string;
  deliverBy: string;
  status: RequestStatus;
  spendPassId: string;
  lines: RequestLine[];
  decision: Decision;
  totalCents?: number;
  /** How many product ids were asked live at Valio. */
  liveChecked: number;
  orderId?: string;
  /** For waiting requests: the one question for the owner. */
  question?: string;
  simulated?: SimulatedMark[];
}

/** One row in the inbox. */
export interface InboxItem {
  id: string;
  createdAt: string;
  text: string;
  status: RequestStatus;
  sentence: string;
  totalCents?: number;
}

export type OrderState = "waiting" | "approved" | "placed" | "rejected";

export interface OrderLine {
  productId: string;
  name: string;
  quantity: number;
  unit: string;
  totalCents: number;
}

/** `confirm_order` / `get_order` result. */
export interface Order {
  id: string;
  requestId: string;
  state: OrderState;
  lines: OrderLine[];
  totalCents: number;
  /** Every state the order went through, oldest first. */
  history: { state: OrderState; at: string }[];
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
  diet?: string[];
  categories: string[];
  deliverBy: string;
  substitutes: string;
  split: { maxExtraCostPct: number; allowListedSubstitutes: boolean };
  disclosed: string[];
  hidden: string[];
}

export type LedgerKind =
  | "request"
  | "decision"
  | "order"
  | "approval"
  | "simulation"
  | "renewal";

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
  | "accepted";

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
}

export interface SteadyOrderSummary {
  id: string;
  name: string;
  weekday: string;
  lineCount: number;
  flagCount: number;
  renewedAt?: string;
}

/** The few demo switches the presenter presses. Each one is simulated. */
export interface DemoState {
  stockOut466375: boolean;
}
