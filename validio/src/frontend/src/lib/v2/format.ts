// v2 formatting: the money and time helpers of src/lib/format.ts, plus the
// day heads and the week line the timeline and Home share.
import type { ActivityItem } from "$lib/api/types";
import { CLOCK, dayTime, hm, money, nb } from "$lib/format";

export { dayTime, hm, money, nb };

const HELSINKI = "Europe/Helsinki";
const ymd = (iso: string) => new Intl.DateTimeFormat("en-CA", { timeZone: HELSINKI }).format(new Date(iso));
const dayWords = (iso: string) =>
  nb(new Intl.DateTimeFormat("en-GB", { weekday: "short", day: "numeric", month: "short", timeZone: HELSINKI }).format(new Date(iso)));

/** "Today, Sat 14 Nov" or "Thu 13 Nov". `now` defaults to the demo clock in the fixture, the real one live. */
export function dayHead(iso: string, now: string = import.meta.env.VITE_API === "live" ? new Date().toISOString() : CLOCK): string {
  const words = dayWords(iso);
  return ymd(iso) === ymd(now) ? `Today, ${words}` : words;
}

/** Timeline items under their day, newest day first; the items keep their order. */
export function byDay(items: ActivityItem[], now?: string): { key: string; head: string; items: ActivityItem[] }[] {
  const out: { key: string; head: string; items: ActivityItem[] }[] = [];
  for (const i of items) {
    const key = ymd(i.at);
    const g = out.find((x) => x.key === key);
    if (g) g.items.push(i);
    else out.push({ key, head: dayHead(i.at, now), items: [i] });
  }
  return out;
}

/** The amount column: "1,515.00 €", or nothing when there is no total. */
export const total = (cents: number | null | undefined): string => (cents == null ? "" : money(cents));

/** "1,190.10 € of 8,000.00 €" or "1,190.10 €" without a weekly cap. */
export const weekText = (used: number, cap: number | null): string => (cap == null ? money(used) : `${money(used)} of ${money(cap)}`);
