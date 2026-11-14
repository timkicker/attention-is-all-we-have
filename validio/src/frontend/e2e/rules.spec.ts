import { test, expect, type Page } from "@playwright/test";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { code, fresh, stockOut } from "./helpers";

// The layout rules of the UI plan v2 (§6), measured on the rendered pages in
// fixture mode. Each route state is walked at each viewport; every check adds
// its failures to one list, so a run names all of them at once.

const VIEWS = [
  { width: 1600, height: 900 },
  { width: 1280, height: 900 },
  { width: 900, height: 900 },
  { width: 390, height: 844 },
];

/** Measures one route state in the browser and returns what breaks a rule. */
function measure(page: Page, name: string) {
  return page.evaluate((name) => {
    const out: string[] = [];
    const fail = (rule: string, what: string) => out.push(`${name} ${innerWidth}: §6.${rule} ${what}`);
    // C is the width the page can use: the viewport less the scrollbar gutter
    // the root reserves (headless Chromium reserves it but still reports it in clientWidth).
    const C = document.querySelector("main")!.getBoundingClientRect().right;
    const W = innerWidth;
    const L = W >= 1328 + 1 ? 208 + (C - 1328) / 2 + 32 : W > 1023 ? 240 : W > 760 ? 80 : 16;
    const near = (a: number, b: number) => Math.abs(a - b) <= 1;
    const box = (e: Element) => e.getBoundingClientRect();
    const shown = (e: Element) => {
      const r = box(e);
      return r.width > 0 && r.height > 0 && !e.closest("[hidden], details:not([open]) > :not(summary)");
    };
    const all = (sel: string) => [...document.querySelectorAll(sel)].filter(shown);
    const label = (e: Element) => `${e.tagName.toLowerCase()}${e.id ? "#" + e.id : ""}.${[...e.classList][0] ?? ""} "${(e as HTMLElement).innerText?.slice(0, 30)}"`;
    const main = document.querySelector("main")!;
    // The boxes a person sees: text runs, pills, icons and plots, not wrappers.
    const leaves = (root: Element) =>
      [...root.querySelectorAll("*")].filter(
        (x) => shown(x) && !x.closest("svg *") && (x.matches("svg, .v-pill, input, [data-slot=button]") || [...x.childNodes].some((n) => n.nodeType === 3 && n.textContent!.trim())),
      ).sort((a, b) => box(a).left - box(b).left);

    // 1. h1 left.
    const h1 = all("main h1");
    if (h1.length !== 1) fail("1", `${h1.length} h1`);
    for (const h of h1) if (!near(box(h).left, L)) fail("1", `h1 left ${box(h).left} not ${L}`);

    // 2. Same left as the h1.
    const phoneBar = (e: Element) => !!e.closest(".kopfleiste");
    for (const e of all("main .crumbs, main .facts, main .lead, main .question, main .q-sub, main .tabs, main h2, main .section-card, main .rc-lane, main .day")) {
      if (phoneBar(e)) continue;
      if (!near(box(e).left, L)) fail("2", `${label(e)} left ${Math.round(box(e).left)} not ${L}`);
    }

    // 3. Card right edge.
    // Approve sits at the prose measure, 680, at every width above the phone.
    const narrow = !!document.querySelector(".wrap.narrow");
    const right = W <= 760 ? C - 16 : narrow ? L + 680 : W >= 1329 ? L + 1056 : C - 32;
    for (const c of all("main .section-card")) if (!near(box(c).right, right)) fail("3", `card right ${box(c).right} not ${right}`);

    // 4. Rows start at card left + 16; 5. titles at card left + 156, pills at + 16.
    for (const c of all("main .section-card")) {
      const cl = box(c).left;
      for (const row of [...c.children].filter(shown)) {
        // The row's content box: its padding edge, or the first thing it shows.
        const inner = row.matches(".v-row, .vr") ? row : row.querySelector(".v-row, .vr");
        const at = inner ? box(inner).left + parseFloat(getComputedStyle(inner).paddingLeft) : leaves(row)[0] ? box(leaves(row)[0]).left : cl + 16;
        if (!near(at, cl + 16)) fail("4", `${label(row)} starts at ${Math.round(at - cl)}`);
      }
      if (W > 760)
        for (const t of c.querySelectorAll(".v-row-title")) if (shown(t) && !near(box(t).left, cl + 156)) fail("5", `title ${label(t)} at ${box(t).left - cl}`);
      for (const p of c.querySelectorAll(".v-row-lead .v-pill")) if (shown(p) && !near(box(p).left, cl + 16)) fail("5", `pill at ${box(p).left - cl}`);
    }

    // 6. Lanes.
    for (const lane of all("main .rc-lane")) {
      const plots = lane.querySelectorAll(".rc-plot");
      if (plots.length !== 1) fail("6", `lane with ${plots.length} plots`);
      const plot = plots[0];
      if (W >= 900) {
        for (const e of lane.querySelectorAll(".rc-n, .rc-v")) if (!near(box(e).left, L)) fail("6", `${label(e)} at ${box(e).left}`);
        if (plot && !near(box(plot).left, L + 200)) fail("6", `plot at ${box(plot).left} not ${L + 200}`);
        if (!near((lane as HTMLElement).clientHeight, 80)) fail("6", `lane height ${box(lane).height}`);
      } else {
        for (const e of [...lane.querySelectorAll(".rc-n, .rc-v")]) if (!near(box(e).left, 16)) fail("6", `${label(e)} at ${box(e).left}`);
        if (plot && !near(box(plot).left, 16)) fail("6", `plot at ${box(plot).left}`);
      }
      const v = lane.querySelector(".rc-v");
      if (v && W >= 900 && (getComputedStyle(v).fontSize !== "14px" || getComputedStyle(v).fontWeight !== "600")) fail("6", `.rc-v ${getComputedStyle(v).fontSize}/${getComputedStyle(v).fontWeight}`);
      // 6a. Labels inside the plot and apart.
      if (plot) {
        const pb = box(plot);
        const labels = [...plot.querySelectorAll(".rc-lbl")].map((l) => ({ l, r: box(l) }));
        for (const { l, r } of labels) {
          if (r.left < pb.left - 1 || r.right > pb.right + 1 || r.top < pb.top - 1 || r.bottom > pb.bottom + 1) fail("6a", `label "${(l as HTMLElement).innerText}" outside its plot`);
          if ((l as HTMLElement).innerText.trim() === "0") fail("6a", "label reads 0");
        }
        for (let i = 0; i < labels.length; i++)
          for (let j = i + 1; j < labels.length; j++) {
            const a = labels[i].r, b = labels[j].r;
            if (a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom) fail("6a", `labels overlap: "${(labels[i].l as HTMLElement).innerText}" and "${(labels[j].l as HTMLElement).innerText}"`);
          }
        const name = lane.querySelector(".rc-n")?.textContent ?? "";
        if (/Total|Limits/.test(name) && !labels.some(({ l }) => /never above/.test(l.textContent ?? ""))) fail("6a", `${name} plot without never above`);
      }
    }
    for (const x of document.querySelectorAll(".rc-xax")) if (!x.closest(".rc-lane")) fail("6", "rc-xax outside a lane");
    // 6b. Value column.
    for (const v of all("main [data-value]")) {
      const cl = box(v.closest(".section-card")!).left;
      const want = W >= 900 ? L + 200 : cl + 16;
      if (!near(box(v).left, want)) fail("6b", `value ${label(v)} at ${box(v).left} not ${want}`);
    }

    // 8. Type.
    const sizes = new Set(["12px", "13px", "14px", "15px", "16px", "24px"]);
    for (const e of main.querySelectorAll("*")) {
      if (!shown(e) || !(e as HTMLElement).innerText?.trim() || e.closest("svg")) continue;
      const own = [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent!.trim());
      if (!own) continue;
      const fs = getComputedStyle(e).fontSize;
      if (!sizes.has(fs)) fail("8", `${label(e)} ${fs}`);
    }
    for (const b of all("[data-slot=button]")) {
      const fs = getComputedStyle(b).fontSize;
      if (fs !== (W <= 760 ? "14px" : "13px")) fail("8", `button ${label(b)} ${fs}`);
    }

    // 9. Hit sizes at 390.
    if (W <= 760)
      for (const e of all("button, summary, [role=tab], input, [role=menuitem], .kopfleiste a, nav.dock a")) {
        const r = box(e);
        if (r.width < 43.5 || r.height < 43.5) fail("9", `${label(e)} ${Math.round(r.width)}×${Math.round(r.height)}`);
      }
    // Inline links in .facts and the lead.
    for (const a of all("main .facts a, main .lead a")) {
      const r = box(a);
      for (const dy of [-20, 0, 20]) {
        const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2 + dy);
        if (W <= 760 && !(hit && a.contains(hit))) fail("9", `link ${label(a)} misses at ${dy}`);
      }
    }

    // 11. Accent walker; 13. no orange.
    const rgb = (s: string) => s.match(/[\d.]+/g)?.map(Number) ?? [];
    const accent = new Set<string>();
    for (const v of ["--valio", "--valio-ink"]) {
      const probe = document.createElement("i");
      probe.style.color = `var(${v})`;
      document.body.append(probe);
      accent.add(getComputedStyle(probe).color);
      probe.remove();
    }
    const allowed = (e: Element, prop: string) =>
      (prop === "background-color" && (e.matches(".v-pill.tone-wait, .v-count") || (e.matches("[data-slot=button]") && document.documentElement.dataset.theme === "light"))) ||
      (prop === "color" && e.matches(".v-pill.tone-wait, .v-count")) ||
      (prop.startsWith("border") && e.matches("[role=tab][aria-selected=true]")) ||
      ((prop === "outline-color" || prop.startsWith("border")) && e.matches(":focus-visible, :focus")) ||
      (prop === "fill" && !!e.closest("[data-plot-subject]")) ||
      (prop === "background-color" && !!e.closest("[data-plot-subject]"));
    let defaults = 0;
    for (const e of document.querySelectorAll("body *")) {
      if (!shown(e)) continue;
      const cs = getComputedStyle(e);
      for (const prop of ["color", "background-color", "border-top-color", "border-bottom-color", "fill", "stroke", "outline-color"]) {
        const val = cs.getPropertyValue(prop);
        if (prop.startsWith("border") && parseFloat(cs.getPropertyValue(prop.replace("color", "width"))) === 0) continue;
        if (prop === "outline-color" && cs.outlineStyle === "none") continue;
        if (prop === "stroke" && cs.stroke === "none") continue;
        if (accent.has(val) && !allowed(e, prop)) fail("11", `${label(e)} ${prop} is the accent`);
        const [r, g, b, a = 1] = rgb(val);
        if (a > 0 && r !== undefined) {
          const mx = Math.max(r, g, b) / 255, mn = Math.min(r, g, b) / 255, l = (mx + mn) / 2, d = mx - mn;
          const s = d === 0 ? 0 : d / (1 - Math.abs(2 * l - 1));
          let h = 0;
          if (d) h = mx === r / 255 ? 60 * (((g - b) / 255 / d) % 6) : mx === g / 255 ? 60 * ((b - r) / 255 / d + 2) : 60 * ((r - g) / 255 / d + 4);
          if (h < 0) h += 360;
          if (h >= 20 && h <= 50 && s > 0.4) fail("13", `${label(e)} ${prop} ${val} is orange`);
        }
      }
      if (e.matches("[data-slot=button]") && !e.matches("[data-variant], .menu-btn") && cs.backgroundColor === getComputedStyle(document.documentElement).getPropertyValue("--primary")) defaults++;
    }
    if (document.querySelectorAll("main [data-slot=button]:not([data-variant=outline]):not([data-variant=ghost])").length > 1 && !document.querySelector(".bar")) {
      // the code bar's Cancel is outline, so a route has at most one default button
      const n = [...document.querySelectorAll("main [data-slot=button]")].filter((b) => shown(b) && getComputedStyle(b).backgroundColor === getComputedStyle(document.querySelector("main [data-slot=button]")!).backgroundColor && !/outline|ghost/.test(b.className)).length;
      if (n > 1 && defaults > 1) fail("11", `${n} default buttons`);
    }

    // 14. Copy.
    const hidden = [...document.querySelectorAll("details:not([open]) > :not(summary), [hidden], [data-raw], details .fold-body")];
    hidden.forEach((e) => ((e as HTMLElement).dataset.was = (e as HTMLElement).style.display, ((e as HTMLElement).style.display = "none")));
    const text = main.innerText;
    hidden.forEach((e) => ((e as HTMLElement).style.display = (e as HTMLElement).dataset.was ?? ""));
    for (const ch of ["·", "–", "—"]) if (text.includes(ch)) fail("14", `"${ch}" in the text`);
    for (const m of text.matchAll(/\b\d{6}\b/g)) fail("14", `six-digit id ${m[0]}`);
    for (const m of text.matchAll(/\b(ST|BAG|EUR|KI|PCS|KPL)\b/g)) fail("14", `unit code ${m[0]}`);
    // Money is "1,010.00 €": no euro sign in front, none glued to the number, no EUR.
    for (const m of text.matchAll(/€\d|\d€|\bEUR\b|\d\.\d{2} ?e\b/g)) fail("14", `money "${m[0]}"`);
    if ((text.match(/out of stock/gi) ?? []).length > 1) fail("14", `"Out of stock" ${(text.match(/out of stock/gi) ?? []).length} times`);

    // 15. Nav names.
    for (const a of document.querySelectorAll("nav a[id^=nav-]")) {
      const vis = (a as HTMLElement).innerText.trim().split("\n")[0];
      const nm = (a.getAttribute("aria-label") ?? (a as HTMLElement).innerText).trim();
      if (vis && !nm.startsWith(vis)) fail("15", `nav "${nm}" does not start with "${vis}"`);
    }

    // 18. Nothing twice.
    for (const h of h1) {
      const t = (h as HTMLElement).innerText.trim();
      if (t.endsWith(".")) fail("18", "h1 ends with a full stop");
      const n = main.innerText.split(t).length - 1;
      if (n > 1 && !document.querySelector(".kopfleiste")) fail("18", `h1 text ${n} times`);
    }
    for (const f of all("main .facts")) if (f.children.length > 4) fail("18", `.facts has ${f.children.length} children`);
    for (const h2 of all("main h2")) {
      const t = (h2.firstChild?.textContent ?? "").trim();
      const card = h2.parentElement?.querySelector(".section-card");
      for (const p of card?.querySelectorAll(".v-pill") ?? []) if ((p as HTMLElement).innerText.trim() === t) fail("18", `h2 "${t}" repeats a pill`);
    }

    // 17. Bottom clearance at 390.
    if (W <= 760) {
      const dock = document.querySelector("nav.dock, .bar");
      if (dock) {
        scrollTo(0, document.documentElement.scrollHeight);
        const top = box(dock).top;
        const last = leaves(main).filter((e) => !e.closest(".bar")).reduce((m, e) => Math.max(m, box(e).bottom), 0);
        if (last > top - 16 + 1) fail("17", `content ends at ${Math.round(last)}, bar at ${Math.round(top)}`);
        scrollTo(0, 0);
      }
      // 22. Back box.
      const back = document.querySelector(".kopfleiste a");
      if (back) {
        const r = box(back);
        if (!near(r.left, 8) || !near(r.right, 52) || !near(r.top, 0) || !near(r.bottom, 48)) fail("22", `back box ${r.left},${r.top} ${r.right},${r.bottom}`);
      }
    }
    return out;
  }, name);
}

for (const v of VIEWS) {
  for (const theme of ["light", "dark"] as const) {
    test(`plan rules at ${v.width} ${theme}`, async ({ page }) => {
      await page.setViewportSize({ width: v.width, height: v.height });
      await page.emulateMedia({ colorScheme: theme });
      const problems: string[] = [];
      const go = async (path: string) => {
        await page.goto(`${path}?theme=${theme}`);
        await page.waitForLoadState("networkidle");
      };
      const check = async (name: string) => {
        await page.waitForTimeout(150);
        problems.push(...(await measure(page, name)));
      };

      await fresh(page);
      await go("/");
      await expect(page.getByTestId("inbox-R-1")).toBeVisible();
      await check("inbox");
      await go("/requests/R-1");
      await expect(page.locator("#request-title")).toBeVisible();
      await check("R-1");
      if (v.width > 760) await stockOut(page);
      else {
        await page.setViewportSize({ width: 1280, height: 900 });
        await stockOut(page);
        await page.setViewportSize({ width: v.width, height: v.height });
      }
      await go("/");
      await expect(page.getByTestId("inbox-R-2")).toBeVisible();
      await check("inbox waiting");
      await go("/requests/R-2");
      await expect(page.getByTestId("open-approve")).toBeVisible();
      await check("R-2 waiting");
      await go("/approve/R-2");
      await expect(page.getByTestId("approve-question")).toBeVisible();
      await check("approve");
      await page.getByTestId("approve").click();
      // 16. Focus goes to the code field, and Enter acts.
      await expect(page.getByTestId("code-input")).toBeFocused();
      await check("approve code");
      await page.getByTestId("code-input").fill("246810");
      await page.keyboard.press("Enter");
      await expect(page.getByTestId("order-steps")).toBeVisible();
      await check("approve done");
      await go("/requests/R-2");
      await expect(page.getByTestId("request-status")).toContainText("Ordered");
      await check("R-2 ordered");
      await go("/steady");
      await expect(page.getByTestId("steady-S-1")).toBeVisible();
      await check("steady list");
      await go("/steady/S-1");
      await expect(page.getByTestId("renew")).toBeVisible();
      await check("steady before");
      await page.getByTestId("renew").click();
      await code(page);
      await expect(page.getByTestId("accept-471376")).toBeVisible();
      await check("steady after");
      await page.getByTestId("accept-471376").click();
      await expect(page.getByTestId("line-471376")).toContainText("Accepted");
      await check("steady accepted");
      await go("/spend-pass");
      await expect(page.locator("#pass-cap")).toBeVisible();
      await check("spend pass");
      await go("/ledger");
      await expect(page.getByTestId("chain-status")).toBeVisible();
      await check("ledger");
      expect(problems, problems.join("\n")).toEqual([]);
    });
  }
}

// 19 and 20. Grep tests over the source.
function files(dir: string, ext: string): string[] {
  return readdirSync(dir).flatMap((f) => {
    const p = join(dir, f);
    return statSync(p).isDirectory() ? files(p, ext) : p.endsWith(ext) ? [p] : [];
  });
}

test("source rules", () => {
  const problems: string[] = [];
  for (const f of files("src", ".svelte")) {
    const s = readFileSync(f, "utf8");
    for (const m of s.matchAll(/#[0-9a-fA-F]{3,8}\b(?![\w-])/g)) if (!/\\u|&#/.test(s.slice(m.index! - 2, m.index!))) problems.push(`${f}: hex ${m[0]}`);
    if (/variant="link"/.test(s)) problems.push(`${f}: variant="link"`);
    if (/html\.light/.test(s)) problems.push(`${f}: html.light`);
    for (const m of s.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)) for (const d of m[1].matchAll(/\b\d+(\.\d+)?m?s\b/g)) problems.push(`${f}: raw duration ${d[0]}`);
  }
  const css = readFileSync("src/app.css", "utf8");
  if (/html\.light/.test(css)) problems.push("app.css: html.light");
  for (const d of css.matchAll(/(transition|animation)[^;]*\b\d+(\.\d+)?m?s\b/g)) problems.push(`app.css: raw duration "${d[0]}"`);
  // Hex only inside the token blocks at the top (before the first rule that is not :root or a theme scope).
  const tokenEnd = css.indexOf("/* ---------- ");
  for (const m of css.slice(tokenEnd).matchAll(/#[0-9a-fA-F]{3,8}\b/g)) problems.push(`app.css: hex ${m[0]} outside the tokens`);
  // The kit's own custom properties are not reassigned.
  const kit = ["vendor/arlen-ui-kit/src/app.css", "vendor/arlen-ui-kit/src/lib/theme-light.css"]
    .flatMap((p) => { try { return [readFileSync(p, "utf8")]; } catch { return []; } })
    .join("\n");
  const kitNames = new Set([...kit.matchAll(/(--[\w-]+)\s*:/g)].map((m) => m[1]));
  // The scoped overrides the plan lists in §2.
  const scoped = /^--(height-[\w-]+|text-sm|text-2xs|text-xs|radius-chip|space-row|shadow-card|primary[\w-]*|ring)$/;
  for (const m of css.matchAll(/(--[\w-]+)\s*:/g)) if (kitNames.has(m[1]) && !scoped.test(m[1])) problems.push(`app.css assigns kit token ${m[1]}`);
  // The focus rule is outside any @layer.
  const focus = css.indexOf(":focus-visible");
  const before = css.slice(0, focus);
  const opened = (before.match(/@layer[^{;]*\{/g) ?? []).length;
  if (opened && before.lastIndexOf("@layer") > before.lastIndexOf("}\n}")) problems.push("app.css: focus rule inside @layer");
  expect(problems, problems.join("\n")).toEqual([]);
});

// The control: the walker must still fail when a rule is broken on purpose.
test("plan rules can fail", async ({ page }) => {
  await fresh(page);
  await page.evaluate(() => {
    const w = document.querySelector("main .wrap")!;
    w.insertAdjacentHTML(
      "beforeend",
      '<p style="color:var(--valio)">accent text</p><p style="font-size:17px">odd size</p><p style="color:rgb(230,140,40)">orange</p><p>Order 466375 · now</p>',
    );
  });
  const out = (await measure(page, "control")).join("\n");
  for (const rule of ["§6.11", "§6.8", "§6.13", "§6.14"]) expect(out).toContain(rule);
});
