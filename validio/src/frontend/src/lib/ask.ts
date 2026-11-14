// The ask dialog's pieces, built from the request the agent made (read back
// by id) and from the agent's steps, never shown raw: one inbox-style row per
// ask, a short line when nothing was asked, and a plain log.
import type { InboxItem, RequestStatus, SupplyRequest } from "./api/types";
import { money } from "./format";

export interface AskRow {
  id: string;
  status: RequestStatus;
  title: string;
  end?: string;
  sub?: string;
}

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
const firstSentence = (s: string) => s.trim().split(/(?<=\.)\s/)[0];

/** A reason in about five words, where the backend's sentence has a known short form. */
export function shortReason(s: string): string {
  const budget = s.match(/over the budget of ([\d,.]+\s?€)/);
  return budget ? `Over the ${budget[1]} budget` : s;
}

/** One row as the inbox shows it: the amount unless blocked, one reason only where the pill does not say it. */
export function askRow(r: SupplyRequest, item?: InboxItem): AskRow {
  const blocked = r.status === "blocked" || r.status === "rejected";
  let sub: string | undefined;
  if (r.status === "waiting") {
    const said = item?.summary ?? r.question;
    sub = said ? shortReason(said).replace(/^Asks you:\s*/, "") : undefined;
  }
  else if (blocked) sub = cap((r.decision.summary ?? r.decision.sentence ?? "").replace(/^Blocked:\s*/i, "")) || undefined;
  return {
    id: r.id,
    status: r.status,
    title: r.titleText ?? r.title ?? r.text,
    end: blocked ? undefined : (r.moneyText ?? (r.totalCents ? money(r.totalCents) : undefined)),
    sub,
  };
}

/** When the agent made no request: one short line from its last words. */
export function notRecorded(final: string): string {
  const m = final.match(/Valio's answers for (.+?) aren't recorded for this demo/);
  return m ? `Not recorded for this demo: ${m[1]}` : firstSentence(final).replace(/^(Not recorded for this demo: .*?)\.$/, "$1");
}

export interface AskStep {
  who: "Kitchen" | "Agent" | "Validio";
  what: string;
}

const DECIDED: Record<string, (id: string) => string> = {
  auto_order: (id) => `${id} may be ordered alone.`,
  ask_human: (id) => `${id} needs you.`,
  block: (id) => `Blocked ${id}.`,
};
const ORDER: Record<string, string> = { placed: "Placed {id}", waiting: "{id} waits for you", rejected: "{id} was rejected" };

/** One ask's steps in plain words: who did what. No tool names, no JSON, no product numbers, no repeats. */
export function askLog(lines: string[]): AskStep[] {
  const out: AskStep[] = [];
  const add = (who: AskStep["who"], what: string) => {
    if (what && !out.some((x) => x.what === what)) out.push({ who, what }); // said once, by whoever said it first
  };
  for (const raw of lines) {
    const parts = raw.split("\n").map((p) => p.trim()).filter(Boolean);
    const head = parts[0];
    if (!head) continue;
    let m: RegExpMatchArray | null;
    if ((m = head.match(/^kitchen\s+(.*)$/))) add("Kitchen", m[1]);
    else if ((m = head.match(/^agent -> (\w+)\s*(.*)$/))) {
      const [, tool, args] = m;
      const id = args.match(/"([ROS]-\d+)"/)?.[1] ?? "";
      if (tool === "request_supply") add("Agent", "Asks Validio");
      else if (tool === "confirm_order") add("Agent", `Confirms ${id}`.trim());
      else if (tool === "get_order") add("Agent", `Checks ${id}`.trim());
      else add("Agent", "Asks Validio");
    } else if (head.startsWith("Validio <- ")) {
      const body = parts[1] ?? "";
      const req = body.match(/^request\s+(R-\d+):\s*\w+,\s*checked (\d+) products? live/);
      const order = body.match(/^order\s+(O-\d+):\s*(\w+),\s*(.+)$/);
      if (req) {
        const code = parts.find((p) => p.startsWith("decision:"))?.match(/^decision:\s*(\w+)/)?.[1] ?? "";
        const checked = req[2] === "0" ? "" : `Checked ${req[2]} products live. `;
        add("Validio", `${checked}${DECIDED[code]?.(req[1]) ?? `${req[1]} recorded.`}`);
      } else if (order) {
        add("Validio", `${(ORDER[order[2]] ?? "{id} " + order[2]).replace("{id}", order[1])}, ${order[3]}`);
      } else if (/^error:/.test(body)) add("Validio", firstSentence(body.replace(/^error:.*?\d{3}[^:]*:\s*/, "")));
    } else if ((m = head.match(/^agent\s+(.*)$/))) add("Agent", firstSentence(m[1]));
  }
  return out;
}
