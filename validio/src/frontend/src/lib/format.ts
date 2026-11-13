// Formatting for money, dates and the words the pages share.
import type { FactGrade, OptionVerdict, RequestStatus, SteadyLineResult } from "./api/types";

const euro = new Intl.NumberFormat("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const money = (cents: number | undefined): string =>
  cents === undefined ? "" : `${euro.format(cents / 100)}\u00a0€`;

const HELSINKI = "Europe/Helsinki";

export const day = (iso: string): string =>
  new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", timeZone: HELSINKI }).format(new Date(iso));

export const time = (iso: string): string =>
  new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit", timeZone: HELSINKI }).format(new Date(iso));

export const dayTime = (iso: string): string =>
  new Intl.DateTimeFormat("en-GB", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: HELSINKI }).format(new Date(iso));

/** How a state is shown. ok and bad are the kit's success and error text,
 *  act is the accent mark with plain text, quiet is secondary text. Nothing is
 *  yellow or amber: a warning is a word, not a colour. */
export type Tone = "ok" | "bad" | "act" | "quiet";

export const STATUS: Record<RequestStatus, { label: string; tone: Tone }> = {
  working: { label: "Working", tone: "quiet" },
  ordered_alone: { label: "Ordered alone", tone: "ok" },
  waiting: { label: "Waiting for you", tone: "act" },
  approved: { label: "Approved", tone: "ok" },
  ordered: { label: "Ordered after approval", tone: "ok" },
  rejected: { label: "Rejected", tone: "bad" },
  blocked: { label: "Blocked", tone: "bad" },
};

export const GRADE: Record<FactGrade, { label: string; tone: Tone }> = {
  attested: { label: "attested", tone: "quiet" },
  attested_until: { label: "attested until", tone: "quiet" },
  consistent: { label: "consistent", tone: "quiet" },
  contradicted: { label: "contradicted", tone: "bad" },
  unchecked: { label: "unchecked", tone: "quiet" },
  unknown: { label: "unknown", tone: "quiet" },
  untrusted: { label: "untrusted", tone: "quiet" },
  missing: { label: "missing", tone: "quiet" },
};

export const VERDICT: Record<OptionVerdict, { label: string; tone: Tone }> = {
  chosen: { label: "Chosen", tone: "ok" },
  ranked: { label: "Ranked", tone: "quiet" },
  // Turned down for not fitting the need is ordinary; only a rule block is loud.
  rejected: { label: "Turned down", tone: "quiet" },
  blocked: { label: "Blocked", tone: "bad" },
  not_deliverable: { label: "Not deliverable", tone: "quiet" },
};

export const LINE_RESULT: Record<SteadyLineResult, { label: string; tone: Tone }> = {
  pending: { label: "Not renewed yet", tone: "quiet" },
  renewed: { label: "Renewed alone", tone: "ok" },
  split_renewed: { label: "Split, renewed alone", tone: "ok" },
  waiting: { label: "Waiting for you", tone: "act" },
  flagged: { label: "Drift flag", tone: "act" },
  accepted: { label: "Accepted", tone: "ok" },
};

/** A label for any state the API sends, also one these maps do not know yet:
 *  then the raw value in words, quiet. A page never crashes on a new state. */
export function look(map: Record<string, { label: string; tone: Tone }>, key: string | undefined): { label: string; tone: Tone } {
  if (key && Object.hasOwn(map, key)) return map[key];
  const words = (key ?? "unknown").replaceAll("_", " ");
  return { label: words.charAt(0).toUpperCase() + words.slice(1), tone: "quiet" };
}

/** Units as words, never the catalogue's "ST" or "PSS". */
export const unitWord = (unit: string, n: number): string => {
  const u = unit.toLowerCase();
  const words: Record<string, [string, string]> = {
    st: ["pack", "packs"],
    kpl: ["pack", "packs"],
    pcs: ["piece", "pieces"],
    bag: ["bag", "bags"],
    ki: ["carton", "cartons"],
    ps: ["bag", "bags"],
    pss: ["bag", "bags"],
    ltk: ["box", "boxes"],
    kg: ["kg", "kg"],
    l: ["litre", "litres"],
  };
  const w = words[u];
  if (!w) return unit;
  return n === 1 ? w[0] : w[1];
};

/** The demo's fixed "now", the backend's VALIDIO_NOW. */
export const CLOCK = "2026-11-14T10:00:00+02:00";

/** A fact's field in words. "label:X" and "claim:X" carry the label or claim. */
export function fieldWord(field: string): string {
  const [kind] = field.split(":");
  const words: Record<string, string> = {
    quantity: "Stock",
    price: "Price",
    cutoff: "Order cut-off",
    reliability: "Delivered as ordered",
    carbon: "Carbon",
    label: "Label",
    claim: "Claim",
    allergens: "Allergens",
    description: "Description",
    key_ingredients: "Ingredients",
    lactose: "Lactose",
    delivery: "Delivery",
  };
  return words[kind] ?? kind.replaceAll("_", " ");
}

const CODE = /^[A-Z_]+$/;
/** A fact's value as a person reads it. */
export function valueWord(field: string, value: unknown): string {
  if (value === undefined || value === null || value === "") return "none given";
  if (typeof value === "boolean") return value ? "yes" : "no";
  const v = String(value);
  if (field === "cutoff" && /^\d{4}-\d\d-\d\dT/.test(v)) return dayTime(v);
  if (field === "quantity" && v.startsWith("1e+10")) return "no limit given";
  if (CODE.test(v)) return v.toLowerCase().replaceAll("_", " ");
  return v.replace(/ (ST|BAG|KI|PCS)$/, (_, u: string) => ` ${unitWord(u, 2)}`);
}

/** "1000 packs", "10 bags": a count and its unit, always together. */
export const amount = (n: number | undefined, unit: string | undefined): string =>
  n === undefined ? "" : `${n.toLocaleString("en-GB")} ${unit ? unitWord(unit, n) : ""}`.trim();
