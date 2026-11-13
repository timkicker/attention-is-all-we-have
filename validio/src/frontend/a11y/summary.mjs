// Prints what `make a11y` found, per page: axe rule (impact, nodes) per variant, Tab stops without
// visible focus, targets under 44 px on the phone, and the keyboard flows that failed.
import { readdirSync, readFileSync } from "node:fs";

const dir = process.argv[2];
const rows = readdirSync(dir).filter((f) => f.endsWith(".json")).map((f) => JSON.parse(readFileSync(`${dir}/${f}`, "utf8")));
const pages = new Map();
for (const r of rows) {
  const key = r.variant === "keyboard" ? `keyboard ${new URL(r.route).pathname}` : r.route;
  if (!pages.has(key)) pages.set(key, []);
  pages.get(key).push(r);
}
let total = 0;
for (const [page, list] of [...pages].sort()) {
  const lines = [];
  for (const r of list.sort((a, b) => a.variant.localeCompare(b.variant))) {
    if (r.error) lines.push(`  keyboard: ${r.error}`);
    for (const v of r.axe) lines.push(`  ${r.variant}: axe ${v.id} (${v.impact}, ${v.nodes} nodes) ${v.targets.slice(0, 2).join(" | ")}`);
    if (r.focus.length) lines.push(`  ${r.variant}: ${r.focus.length} Tab stops without visible focus: ${r.focus.slice(0, 4).join(", ")}`);
    if (r.targets.length) lines.push(`  ${r.variant}: ${r.targets.length} targets under 44 px: ${r.targets.slice(0, 4).join(", ")}`);
  }
  total += lines.length;
  console.log(`${page}: ${lines.length ? `${lines.length} findings` : "clean"}`);
  for (const l of lines) console.log(l);
}
console.log(`a11y: ${rows.length} results, ${total} findings`);
