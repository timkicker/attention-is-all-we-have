// The Rules in the kitchen's words, and the edit form's parsing. The view and
// the edit page share them, so a value reads the same on both.
import type { Rules } from "$lib/api/types";
import { money } from "$lib/v2";

/** The biggest amount the server takes (RulesIn, MAX_CENTS). */
export const MAX_CENTS = 10_000_000;
export const MAX_EXTRA_PCT = 20;

export type Allowed = "off" | "listed";
export const ALLOWED: { value: Allowed; label: string }[] = [
  { value: "off", label: "Never" },
  { value: "listed", label: "From Valio's list" },
];

/** "lactose-free" reads "Lactose-free". */
export const word = (w: string) => w.charAt(0).toUpperCase() + w.slice(1);

/** "Nuts", "Nuts and fish", "Nuts, fish and soy": one list, no comma before "and". */
export function list(words: string[]): string {
  const w = words.map((x, i) => (i === 0 ? word(x) : x));
  return w.length < 2 ? (w[0] ?? "") : `${w.slice(0, -1).join(", ")} and ${w[w.length - 1]}`;
}

export const allowedOf = (r: Pick<Rules, "substitutes">): Allowed => (r.substitutes === "off" ? "off" : "listed");

export const upTo = (cents: number) => `Up to ${money(cents)}`;
export const extraText = (pct: number) => (pct > 0 ? `Up to ${pct} %` : "None");

/** "1,200.00" for a field: the amount without the euro sign, which sits beside the field. */
export const amountText = (cents: number) => money(cents).replace(/\s*€$/, "");

/**
 * What the owner typed as euros, in cents. "1500", "1,500", "1 500.50" and
 * "1,500.00 €" are all fine; anything else is a problem, said in a few words.
 */
export function parseAmount(raw: string): { cents: number } | { problem: string } {
  const s = raw.replace(/[\s €]/g, "");
  if (!s) return { problem: "Type an amount." };
  if (!/^(\d{1,3}(,\d{3})+|\d+)(\.\d{1,2})?$/.test(s)) return { problem: "Type an amount, like 1,200.00." };
  const cents = Math.round(Number(s.replace(/,/g, "")) * 100);
  if (cents > MAX_CENTS) return { problem: `At most ${money(MAX_CENTS)}.` };
  return { cents };
}

export function parsePct(raw: string): { pct: number } | { problem: string } {
  const s = raw.replace(/[\s%]/g, "");
  if (!/^\d{1,2}$/.test(s) || Number(s) > MAX_EXTRA_PCT) return { problem: `A whole number from 0 to ${MAX_EXTRA_PCT}.` };
  return { pct: Number(s) };
}
