import { writeFileSync } from "node:fs";
import AxeBuilder from "@axe-core/playwright";
import { test, expect, type Page } from "@playwright/test";

// Every route at 1280 and 390 px, light and dark: axe-core with the WCAG 2.2 A and AA rules (colour
// contrast AA included), every Tab stop has a visible focus indicator, and on the phone every target is
// at least 44 x 44 px. Then approve, renew and accept by keyboard only. Then the pages those changed,
// once more. Each test writes what it found to artifacts/a11y/results/<name>.json.

const CODE = process.env.A11Y_CODE!;
const OUT = `${process.env.A11Y_OUT}/results`;
const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];
const VIEWPORTS = { desktop: { width: 1280, height: 900 }, phone: { width: 390, height: 844 } };
const SCHEMES = ["light", "dark"] as const;
const BEFORE = ["/", "/requests/R-1", "/requests/R-2", "/approve/R-2", "/orders", "/steady/S-1", "/ledger"];
const AFTER = ["/approve/R-2", "/steady/S-1", "/ledger"]; // after the keyboard approve, renew and accept

type Found = { route: string; variant: string; axe: object[]; focus: string[]; targets: string[]; error?: string };

const slug = (s: string) => s.replace(/[^a-z0-9]+/gi, "-").replace(/^-|-$/g, "") || "root";
const save = (name: string, f: Found) => writeFileSync(`${OUT}/${slug(name)}.json`, JSON.stringify(f, null, 1));

async function open(page: Page, route: string, scheme: "light" | "dark") {
  await page.emulateMedia({ colorScheme: scheme });
  await page.goto(route);
  // the kit switches on data-theme; the rebuilt app may follow prefers-color-scheme, both are set
  await page.evaluate((s) => document.documentElement.setAttribute("data-theme", s), scheme);
  await page.waitForLoadState("networkidle");
}

const describe = (el: Element) => {
  const id = el.getAttribute("data-testid") || el.id;
  const text = (el.textContent || el.getAttribute("aria-label") || "").trim().replace(/\s+/g, " ").slice(0, 40);
  return `${el.tagName.toLowerCase()}${id ? `#${id}` : ""}${text ? ` "${text}"` : ""}`;
};

// Tab through the page. A stop whose outline, box-shadow, border and background look the same focused
// and unfocused has no visible focus indicator (Tailwind v4 rings always set a box-shadow, so only
// the difference counts).
async function focusGaps(page: Page, stops = 40): Promise<string[]> {
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
  const gaps: string[] = [];
  const seen = new Set<string>();
  for (let i = 0; i < stops; i++) {
    await page.keyboard.press("Tab");
    const r = await page.evaluate((describeSrc) => {
      const el = document.activeElement as HTMLElement | null;
      if (!el || el === document.body) return null;
      const d = new Function(`return (${describeSrc})`)()(el) as string;
      const look = () => {
        const s = getComputedStyle(el);
        return [s.outlineStyle, s.outlineWidth, s.outlineColor, s.boxShadow, s.borderColor, s.backgroundColor,
          s.textDecorationLine].join("|");
      };
      const focused = look();
      el.blur();
      const plain = look();
      el.focus();
      return { d, visible: focused !== plain };
    }, describe.toString());
    if (!r) break;
    if (seen.has(r.d)) break; // wrapped around
    seen.add(r.d);
    if (!r.visible) gaps.push(r.d);
  }
  return gaps;
}

// visible interactive elements smaller than 44 x 44 px; a link inside running text is exempt (WCAG 2.5.5)
async function smallTargets(page: Page): Promise<string[]> {
  return page.evaluate((describeSrc) => {
    const d = new Function(`return (${describeSrc})`)() as (el: Element) => string;
    const sel = "a[href], button, input:not([type=hidden]), select, textarea, [role=button], [role=link], [tabindex]:not([tabindex='-1'])";
    const out: string[] = [];
    for (const el of Array.from(document.querySelectorAll(sel))) {
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0 || getComputedStyle(el).visibility === "hidden") continue;
      const inline = el.tagName === "A" && getComputedStyle(el).display === "inline"
        && (el.parentElement?.textContent || "").trim().length > (el.textContent || "").trim().length;
      if (inline) continue;
      if (r.width < 44 || r.height < 44) out.push(`${d(el)} ${Math.round(r.width)}x${Math.round(r.height)}`);
    }
    return out;
  }, describe.toString());
}

function scan(phase: string, route: string) {
  for (const [vp, size] of Object.entries(VIEWPORTS)) {
    for (const scheme of SCHEMES) {
      const name = `${phase} ${route} ${vp} ${scheme}`;
      test(name, async ({ page }) => {
        await page.setViewportSize(size);
        await open(page, route, scheme);
        const axe = await new AxeBuilder({ page }).withTags(TAGS).analyze();
        const violations = axe.violations.map((v) => ({
          id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.length,
          targets: v.nodes.slice(0, 5).map((n) => n.target.join(" ")),
        }));
        const focus = await focusGaps(page);
        const targets = vp === "phone" ? await smallTargets(page) : [];
        save(name, { route, variant: `${phase} ${vp} ${scheme}`, axe: violations, focus, targets });
        expect.soft(violations, "axe WCAG 2.2 AA violations").toEqual([]);
        expect.soft(focus, "Tab stops without a visible focus indicator").toEqual([]);
        expect.soft(targets, "targets under 44 x 44 px on the phone").toEqual([]);
      });
    }
  }
}

// Keyboard only: Tab to the control, Enter, type the code if a field takes the focus or comes next, Enter.
// When the keyboard cannot do it the step is done by API so the next flows have their state, and the
// test fails with the reason.

const pick = (id: string) => `[data-testid="${id}"], #${id}`;

async function tabTo(page: Page, selector: string, max = 80): Promise<boolean> {
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
  for (let i = 0; i < max; i++) {
    await page.keyboard.press("Tab");
    if (await page.evaluate((s) => !!document.activeElement?.closest(s), selector)) return true;
  }
  return false;
}

async function keyboard(page: Page, id: string, done: () => Promise<boolean>, fallback: () => Promise<boolean>) {
  const problems: string[] = [];
  if (!(await tabTo(page, pick(id)))) problems.push(`${id} is not reachable with Tab`);
  else {
    await page.keyboard.press("Enter");
    const code = pick("code-input");
    await page.waitForTimeout(500);
    const focused = await page.evaluate((s) => !!document.activeElement?.matches(s), code);
    if (focused || (await page.locator(code).count()) > 0) {
      if (!focused) {
        await page.keyboard.press("Tab");
        if (!(await page.evaluate((s) => !!document.activeElement?.matches(s), code)))
          problems.push("the code field does not take the focus and is not the next Tab stop");
      }
      await page.keyboard.type(CODE);
      await page.keyboard.press("Enter");
    }
    await page.waitForLoadState("networkidle");
    if (problems.length === 0 && !(await done()))
      problems.push(`Enter on ${id} did not do it (no code field the keyboard reaches, or the request failed)`);
  }
  if (problems.length) {
    expect(await fallback(), `${id} by API`).toBe(true);
    save(`keyboard ${id}`, { route: page.url(), variant: "keyboard", axe: [], focus: [], targets: [], error: problems.join("; ") });
  }
  expect(problems, `keyboard-only ${id}`).toEqual([]);
}

const api = (page: Page, path: string, post = false) =>
  page.evaluate(async ([p, m, c]) => {
    const r = await fetch(p, { method: m, headers: { "X-Approve-Code": c, accept: "application/json" } });
    return { ok: r.ok, body: await r.json().catch(() => null) };
  }, [path, post ? "POST" : "GET", CODE] as const);

for (const route of BEFORE) scan("before", route);

test("keyboard: approve O-2 with the code on the phone", async ({ page }) => {
  await page.setViewportSize(VIEWPORTS.phone);
  await open(page, "/approve/R-2", "light");
  await keyboard(page, "approve", async () => (await api(page, "/api/orders/O-2")).body?.state === "placed",
    async () => (await api(page, "/api/orders/O-2/approve", true)).ok);
});

test("keyboard: renew S-1", async ({ page }) => {
  await page.setViewportSize(VIEWPORTS.desktop);
  await open(page, "/steady/S-1", "light");
  await keyboard(page, "renew", async () => !!(await api(page, "/api/steady/S-1")).body?.renewedAt,
    async () => (await api(page, "/api/steady/S-1/renew", true)).ok);
});

test("keyboard: accept the pancakes line", async ({ page }) => {
  await page.setViewportSize(VIEWPORTS.desktop);
  await open(page, "/steady/S-1", "light");
  const pan = async () => (await api(page, "/api/steady/S-1")).body?.lines
    ?.find((l: { productId: string }) => l.productId === "471376")?.result;
  await keyboard(page, "accept-471376", async () => (await pan()) === "accepted",
    async () => (await api(page, "/api/steady/S-1/lines/471376/accept", true)).ok);
});

for (const route of AFTER) scan("after", route);
