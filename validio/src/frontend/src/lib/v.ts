// Words and groupings the plan-v2 pages share. Where the backend writes a
// display field it wins; the pattern fallbacks below bridge until it does.
import type { LedgerEntry, LedgerKind, RankedOption, RequestStatus, SteadyLine, SteadyOrder } from "./api/types";
import { money, nb } from "./format";

export type PillTone = "ok" | "wait" | "bad" | "neutral";
export interface Pill {
  label: string;
  tone: PillTone;
}

export const REQUEST_PILL: Record<RequestStatus, Pill> = {
  working: { label: "Working", tone: "neutral" },
  ordered_alone: { label: "Ordered alone", tone: "ok" },
  waiting: { label: "Waiting for you", tone: "wait" },
  approved: { label: "Ordered", tone: "ok" },
  ordered: { label: "Ordered", tone: "ok" },
  rejected: { label: "Rejected", tone: "bad" },
  blocked: { label: "Blocked", tone: "bad" },
};

/** The states nothing more happens in. Every other state, "working" too, is still open. */
const FINAL: ReadonlySet<string> = new Set<RequestStatus>(["ordered_alone", "approved", "ordered", "rejected", "blocked"]);
export const isFinal = (s: string | undefined): boolean => !!s && FINAL.has(s);

export function requestPill(s: string | undefined): Pill {
  return (s && (REQUEST_PILL as Record<string, Pill>)[s]) || { label: words(s), tone: "neutral" };
}

function words(s: string | undefined): string {
  const w = (s ?? "unknown").replaceAll("_", " ");
  return w.charAt(0).toUpperCase() + w.slice(1);
}

/** The pill of an option row: the chosen one and the plain refusals carry a word. */
export function optionPill(o: RankedOption): Pill | null {
  if (o.verdict === "chosen") return { label: "Chosen", tone: "ok" };
  if (o.verdict === "blocked") return { label: "Blocked", tone: "bad" };
  if (o.verdict === "not_deliverable") return { label: "Not deliverable", tone: "neutral" };
  return null;
}

/** The short line under an option's name: the backend writes it. */
export const optionLine = (o: RankedOption): string => nb(o.shortText ?? o.sentence);

/** Turned-down options under the backend's headings, by groupOrder, then groupText. */
export function turnedDownGroups(list: RankedOption[]): { name: string; items: RankedOption[] }[] {
  const groups = new Map<string, { name: string; order: number; items: RankedOption[] }>();
  for (const o of list) {
    const name = o.groupText ?? "Turned down";
    const g = groups.get(name) ?? { name, order: o.groupOrder ?? 99, items: [] };
    g.items.push(o);
    groups.set(name, g);
  }
  return [...groups.values()].sort((a, b) => a.order - b.order || a.name.localeCompare(b.name));
}

/** The ledger actor word from the entry's kind. */
export const ACTOR: Record<LedgerKind, string> = {
  order: "Validio",
  request: "Agent",
  decision: "Validio",
  approval: "Owner",
  simulation: "Demo",
  renewal: "Validio",
};

/** Ledger entries under the request or steady order they belong to, in chain order. */
export function ledgerGroups(entries: LedgerEntry[]): { id: string; entries: LedgerEntry[] }[] {
  const out: { id: string; entries: LedgerEntry[] }[] = [];
  for (const e of [...entries].sort((a, b) => a.seq - b.seq)) {
    const id = e.requestId ?? "";
    const g = out.find((x) => x.id === id);
    if (g) g.entries.push(e);
    else out.push({ id, entries: [e] });
  }
  return out;
}

/** The steady list pill and the right column, from the order's lines. */
export function steadyLook(o: SteadyOrder | undefined, state: string | undefined): { pill: Pill; right: string } {
  const lines: SteadyLine[] = o?.lines ?? [];
  const n = lines.length;
  if (!o || state !== "renewed") return { pill: { label: "Not renewed yet", tone: "neutral" }, right: `${n} lines` };
  const open = lines.filter((l) => l.result === "waiting").length;
  const done = lines.filter((l) => ["renewed", "split_renewed", "accepted"].includes(l.result)).length;
  if (open) return { pill: { label: "Waiting for you", tone: "wait" }, right: `${open} of ${n} lines open` };
  if (done < n) return { pill: { label: `${done} of ${n} ordered`, tone: "neutral" }, right: "" };
  return { pill: { label: "Renewed", tone: "ok" }, right: `${n} lines` };
}

export const euros = money;
