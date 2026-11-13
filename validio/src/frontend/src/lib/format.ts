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

/** Hours and minutes, for lists; seconds only where order matters (ledger, steps). */
export const hm = (iso: string): string =>
  new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: HELSINKI }).format(new Date(iso));

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
  return prose(v.replace(/ (ST|BAG|KI|PCS)$/, (_, u: string) => ` ${unitWord(u, 2)}`)).replaceAll(/\b[A-ZÄÖÅ]{4,}\b/g, (w) => w.toLowerCase());
}

/** "1000 packs", "10 bags": a count and its unit, always together. */
export const amount = (n: number | undefined, unit: string | undefined): string =>
  n === undefined ? "" : unit ? `${n.toLocaleString("en-GB")}\u00a0${unitWord(unit, n)}` : n.toLocaleString("en-GB");

const UNIT_CODE = /\b(\d[\d,]*) (ST|BAG|KI|PCS|KPL|PS|PSS|LTK)\b/g;
const CAPS_RUN = /\b[A-ZÄÖÅ][A-ZÄÖÅ-]{2,}(?:\s+[A-ZÄÖÅ0-9][A-ZÄÖÅ0-9-]+)*\b/g;

/** A catalogue name as a person reads it: no ®, a run of capitals in
 *  sentence case, a space before g, kg and l. The catalogue name itself stays
 *  in the facts. */
export function nameWord(n: string): string {
  return n
    .replaceAll(/[®™]/g, "")
    .replaceAll(CAPS_RUN, (run) => (run.length <= 3 ? run : run.charAt(0) + run.slice(1).toLowerCase()))
    .replaceAll(/(\d)(g|kg|l)\b/g, "$1 $2")
    .replaceAll(/\s{2,}/g, " ")
    .trim();
}

/** A backend sentence in display words: unit codes as unit words, amounts in
 *  euro through money(), a product number dropped where its name follows,
 *  catalogue names cleaned. A field the backend already wrote for display
 *  passes through the same steps unchanged. */
export function prose(s: string | undefined): string {
  if (!s) return "";
  return nameWord(
    s
      .replaceAll(UNIT_CODE, (_, n: string, u: string) => amount(Number(n.replaceAll(",", "")), u))
      .replaceAll(/\b(\d+(?:\.\d+)?) (?:EUR|euro)\b/g, (_, n: string) => money(Math.round(Number(n) * 100)))
      .replaceAll(/\b(\d{4,}) (litres|kg)\b/g, (_, n: string, u: string) => `${Number(n).toLocaleString("en-GB")} ${u}`)
      .replaceAll(/\bof (\d{6}) (?=[A-Z])/g, "of "),
  );
}

/** The sentences of a backend text, one by one, without the same sentence twice. */
export function sentences(s: string | undefined): string[] {
  const out: string[] = [];
  for (const part of prose(s).split(/(?<=[.?!])\s+|;\s+/)) {
    const t = part.trim();
    if (!t) continue;
    const w = t.charAt(0).toUpperCase() + t.slice(1);
    const key = w.toLowerCase().replace(/[.?!]$/, "");
    if (!out.some((o) => o.toLowerCase().replace(/[.?!]$/, "") === key)) out.push(/[.?!]$/.test(w) ? w : `${w}.`);
  }
  return out;
}

/** A request's title in the kitchen's words. The agent may send only a count,
 *  a unit code and a product number ("200 BAG of 466375"); then the product's
 *  name from the options stands in for the number. */
export function requestTitle(r: {
  displayName?: string;
  text: string;
  lines?: { options?: { productId: string; name: string }[] }[];
}): string {
  if (r.displayName) return r.displayName;
  const m = /^(\d+) ([A-Za-z]+) of (\d{6})$/.exec(r.text.trim());
  if (m) {
    const o = (r.lines ?? []).flatMap((l) => l.options ?? []).find((x) => x.productId === m[3]);
    if (o) return `${amount(Number(m[1]), m[2])} of ${nameWord(o.name)}`;
  }
  return prose(r.text);
}

/** A principal id in words: "agent:buyer-1" is "Buyer agent 1", "kitchen:chef"
 *  is "Chef", "validio" is "Validio". The raw id stays for an (i). */
export function holderWord(id: string): string {
  const cap = (w: string) => w.charAt(0).toUpperCase() + w.slice(1);
  const [kind, name] = id.includes(":") ? id.split(":", 2) : ["", id];
  if (kind === "agent") {
    const m = /^([a-z]+)-?(\d+)?$/i.exec(name);
    if (m) return `${cap(m[1])} agent${m[2] ? ` ${m[2]}` : ""}`;
    return "Agent";
  }
  if (name === "presenter") return "Demo";
  return cap(name.replaceAll("-", " "));
}
