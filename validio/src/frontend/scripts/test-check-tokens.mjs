// Control for check-tokens.mjs: a throwaway tree with the defects that happened goes red
// with one line each, the same tree written correctly goes green, an empty tree exits 2.
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

const check = new URL("./check-tokens.mjs", import.meta.url).pathname;
const run = (root) => spawnSync(process.execPath, [check, root], { encoding: "utf8" });
let failed = 0;
const expect = (what, ok) => {
  console.log(`${ok ? "ok  " : "FAIL"} ${what}`);
  if (!ok) failed++;
};

function tree(files) {
  const root = mkdtempSync(join(tmpdir(), "check-tokens-"));
  for (const [p, body] of Object.entries(files)) {
    mkdirSync(join(root, p, ".."), { recursive: true });
    writeFileSync(join(root, p), body);
  }
  return root;
}

const tokens = { "src/lib/tokens.css": ":root { --v-ok: #8fb38a; --radius-chip: 4px; --v-wash: color-mix(in srgb, #fff 5%, transparent); }" };
const bad = tree({
  ...tokens,
  "src/app.css": ".v-pill { --radius-chip: 999px; }\n.box { border-radius: 6px; background: color-mix(in srgb, var(--v-fg) 8%, transparent); }",
  "src/lib/A.svelte": [
    '<div class="rounded-full bg-[#123456] text-red-500" fill="#fff"></div>',
    "<style>",
    "  .t { box-shadow: 0 1px 2px rgba(0, 0, 0, 0.3); color: white; }",
    "</style>",
  ].join("\n"),
});
const r = run(bad);
const lines = r.stderr.trim().split("\n");
expect("planted tree exits 1", r.status === 1);
for (const want of [
  "src/app.css:1: radius \"--radius-chip: 999px\"",
  "src/app.css:2: radius \"border-radius: 6px\"",
  "src/app.css:2: colour \"background: color-mix",
  'src/lib/A.svelte:1: class "rounded-full"',
  'src/lib/A.svelte:1: class "bg-[#"',
  'src/lib/A.svelte:1: fill="#fff"',
  "src/lib/A.svelte:3: colour \"box-shadow",
  "src/lib/A.svelte:3: colour \"color: white\"",
])
  expect(`names ${want}`, lines.some((l) => l.startsWith(want)));
expect("tokens.css itself is never reported", !r.stderr.includes("tokens.css"));
rmSync(bad, { recursive: true });

const good = tree({
  ...tokens,
  "src/app.css": ".v-pill { border-radius: var(--radius-chip); white-space: nowrap; background: var(--v-wash); }\n.x { border-radius: max(0px, calc(var(--radius-card) - 1px)); }",
  "src/lib/A.svelte": [
    '<div class="rounded-chip text-sm" fill="url(#p)"><a href="#face">x</a></div>',
    "<script>const c = '#fff';</script>",
    "<style>",
    "  /* was #fff */ .t { color: var(--v-ok); border-radius: 0; }",
    "</style>",
  ].join("\n"),
});
const g = run(good);
expect(`written correctly exits 0 (${g.stderr.trim() || "no output"})`, g.status === 0);
rmSync(good, { recursive: true });

const empty = tree({ "README": "" });
expect("a tree with nothing to read exits 2", run(empty).status === 2);
rmSync(empty, { recursive: true });

process.exit(failed ? 1 : 0);
