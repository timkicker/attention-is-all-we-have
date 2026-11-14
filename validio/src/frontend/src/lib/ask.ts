// The ask dialog's summary: at most three short lines, built from the request
// the agent made (read back by id), never from the agent's log.
import type { SupplyRequest } from "./api/types";
import { money } from "./format";

const ENDING: Partial<Record<SupplyRequest["status"], string>> = {
  ordered_alone: "Ordered alone",
  ordered: "Ordered",
  approved: "Ordered",
  waiting: "Waits for you",
  blocked: "Blocked",
  rejected: "Blocked",
};

const lower = (s: string) => s.charAt(0).toLowerCase() + s.slice(1);

export function askSummary(r: SupplyRequest): string[] {
  const out = [`Agent asked Validio for ${r.title ?? r.titleText ?? r.text}.`];
  const ids = r.liveChecked?.ids;
  if (ids) out.push(`Checked ${ids} ${ids === 1 ? "product" : "products"} live.`);
  const head = ENDING[r.status];
  if (!head) return out;
  const picked = r.lines.flatMap((l) => {
    const o = l.chosen && l.options.find((x) => x.productId === l.chosen!.productId);
    return o ? [`${o.quantity ?? l.chosen!.salesQty} × ${o.displayName ?? o.name}, ${o.moneyText ?? money(o.totalCents)}`] : [];
  });
  if (head === "Blocked" || !picked.length) out.push(`${head}: ${lower(r.decision.summary ?? r.decision.sentence ?? "nothing was ordered").replace(/\.?$/, ".")}`);
  else out.push(`${head}: ${picked.join("; ")}.`);
  return out;
}
