// Colours and corner radii come from src/lib/tokens.css or the Arlen ui-kit, nowhere else.
// Tim, 14 Nov: "colors are not standartised and corner radius is also not common
// (especially tags and toggles)". The defect was 999px pills beside 4px chips, a
// hand-copied rgba shadow and seven strengths of the same grey wash.
//
// Reads every .svelte and .css under <root>/src (default: this app) except
// src/lib/tokens.css, and fails on:
//   in CSS (a .css file or a <style> block):
//     a colour literal (#hex, rgb(), hsl(), oklch(), lab(), a named colour) or a color-mix(),
//     a radius (any property or custom property with "radius" in its name) that is not 0
//     or built on var(--radius-*);
//   in markup: Tailwind rounded-* other than the kit's role names, Tailwind palette or
//     arbitrary colours, and a colour literal in fill/stroke/color/style attributes.
// Not looked at: .ts files (no colour in them on 14 Nov), the vendored kit, inline SVG
// drawn from a string. Usage: node scripts/check-tokens.mjs [root]
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const root = process.argv[2] ?? new URL("..", import.meta.url).pathname;
const src = join(root, "src");
const TOKENS = join(src, "lib", "tokens.css");

const NAMED =
  "white|black|red|green|blue|gray|grey|orange|yellow|purple|pink|silver|navy|teal|maroon|olive|lime|aqua|fuchsia|beige|brown|gold|ivory|indigo|violet|cyan|magenta|tan|salmon|coral|crimson";
const COLOR = new RegExp(`#[0-9a-fA-F]{3,8}\\b|\\b(rgba?|hsla?|oklch|oklab|lab|lch|hwb|color-mix)\\(|(?<![\\w-])(${NAMED})(?![\\w-])`, "i");
const RADIUS_OK = /^(0|0px|inherit|initial|unset)$|var\(--radius-/;
const TW_ROUND = /(?<![\w-])rounded(-[trblse]{1,2})?-(none|xs|sm|md|lg|xl|2xl|3xl|full|\[)/;
const TW_COLOR = new RegExp(
  `(?<![\\w-])(bg|text|border|fill|stroke|ring|outline|from|via|to|shadow|decoration|accent|caret)-(\\[(#|rgb|hsl|oklch)|(${NAMED}|slate|zinc|neutral|stone|amber|emerald|sky|rose)(-\\d{2,3})?(?![\\w-]))`,
);
const ATTR_COLOR = /\b(fill|stroke|color|stop-color|style)="([^"]*)"/g;

function files(dir) {
  const out = [];
  for (const n of readdirSync(dir)) {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) out.push(...files(p));
    else if (/\.(svelte|css)$/.test(n) && p !== TOKENS) out.push(p);
  }
  return out;
}

const lineOf = (text, i) => text.slice(0, i).split("\n").length;
const problems = [];

function checkCss(file, text, offset, whole) {
  const css = text.replace(/\/\*[\s\S]*?\*\//g, (c) => c.replace(/[^\n]/g, " "));
  for (const m of css.matchAll(/(^|[{;\s])(--?[\w-]+|[a-z-]+)\s*:\s*([^;{}]+)(?=[;}])/g)) {
    const [, , prop, raw] = m;
    const value = raw.trim();
    const at = lineOf(whole, offset + m.index + m[1].length);
    if (prop.includes("radius") && !RADIUS_OK.test(value)) problems.push(`${file}:${at}: radius "${prop}: ${value}" is not on var(--radius-*)`);
    // "white-space: nowrap" names a property, not a colour: only values are read.
    if (COLOR.test(value) && !/^url\(/.test(value)) problems.push(`${file}:${at}: colour "${prop}: ${value}" is not a token`);
  }
}

const all = existsSync(src) ? files(src) : [];
for (const p of all) {
  const text = readFileSync(p, "utf8");
  const file = relative(root, p);
  if (p.endsWith(".css")) {
    checkCss(file, text, 0, text);
    continue;
  }
  let markup = text.replace(/<script[\s\S]*?<\/script>/g, (s) => s.replace(/[^\n]/g, " "));
  for (const m of markup.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)) checkCss(file, m[1], m.index + m[0].indexOf(">") + 1, text);
  markup = markup.replace(/<style[\s\S]*?<\/style>/g, (s) => s.replace(/[^\n]/g, " ")).replace(/<!--[\s\S]*?-->/g, (s) => s.replace(/[^\n]/g, " "));
  for (const [n, line] of markup.split("\n").entries()) {
    const r = TW_ROUND.exec(line);
    if (r) problems.push(`${file}:${n + 1}: class "${r[0]}" is not a kit radius (rounded-chip/button/input/card/modal)`);
    const c = TW_COLOR.exec(line);
    if (c) problems.push(`${file}:${n + 1}: class "${c[0]}" is a colour outside the tokens`);
    for (const a of line.matchAll(ATTR_COLOR)) {
      const v = a[2].replace(/url\(#[^)]*\)/g, "");
      if (COLOR.test(v)) problems.push(`${file}:${n + 1}: ${a[1]}="${a[2]}" is a colour outside the tokens`);
    }
  }
}

if (!all.length) {
  console.error(`check-tokens: NOTHING WAS READ under ${src}`);
  process.exit(2);
}
for (const p of problems) console.error(p);
console.log(
  `check-tokens: ${all.length} .svelte/.css files read, ${problems.length} colour or radius literal(s) outside src/lib/tokens.css. ` +
    "Not read: .ts files, the vendored kit.",
);
process.exit(problems.length ? 1 : 0);
