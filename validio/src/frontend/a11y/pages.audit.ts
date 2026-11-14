import { generateKeyPairSync } from "node:crypto";
import { writeFileSync } from "node:fs";
import AxeBuilder from "@axe-core/playwright";
import { test, expect, type Page } from "@playwright/test";

// Every v2 route at 1280 and 390 px, light and dark: axe-core with the WCAG 2.2 A and AA rules (colour
// contrast AA included), every Tab stop has a visible focus indicator, and on the phone every target is
// at least 44 x 44 px. The Agent page in each of its states (none, pairing, consent, active, paused), Home
// before and after the agent is connected, Login without a session. Approve, connect and allow by keyboard
// only. Each test writes what it found to artifacts/a11y/results/<name>.json.

const BASE = process.env.A11Y_BASE!;
const CODE = process.env.A11Y_CODE!;
const OUT = `${process.env.A11Y_OUT}/results`;
const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];
const VIEWPORTS = { desktop: { width: 1280, height: 900 }, phone: { width: 390, height: 844 } };
const SCHEMES = ["light", "dark"] as const;
// R-1 ordered alone, R-2 waiting for approval, S-1 the Steady Order (setup.ts)
const PAGES = ["/", "/activity", "/activity/R-1", "/activity/R-2", "/activity/S-1", "/rules", "/rules/edit", "/settings"];
const STATES = ["none", "pairing", "consent", "active", "paused"] as const;
type AgentState = (typeof STATES)[number];

type Found = { route: string; variant: string; axe: object[]; focus: string[]; targets: string[]; error?: string };

const slug = (s: string) => s.replace(/[^a-z0-9]+/gi, "-").replace(/^-|-$/g, "") || "root";
const save = (name: string, f: Found) => writeFileSync(`${OUT}/${slug(name)}.json`, JSON.stringify(f, null, 1));

async function open(page: Page, route: string, scheme: "light" | "dark") {
  await page.emulateMedia({ colorScheme: scheme }); // the app follows the system theme until one is chosen
  await page.goto(route);
  await page.waitForLoadState("networkidle");
  if (route !== "/login" && new URL(page.url()).pathname === "/login") throw new Error(`${route} sent to /login: no session`);
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
      // a hit area widened by an absolutely placed ::before or ::after (inset: -10px) counts
      let w = r.width, h = r.height;
      for (const pseudo of ["::before", "::after"]) {
        const p = getComputedStyle(el, pseudo);
        if (p.content === "none" || p.position !== "absolute") continue;
        const px = (v: string) => (v.endsWith("px") ? parseFloat(v) : 0);
        w = Math.max(w, r.width - px(p.left) - px(p.right), parseFloat(p.width) || 0);
        h = Math.max(h, r.height - px(p.top) - px(p.bottom), parseFloat(p.height) || 0);
      }
      if (w < 44 || h < 44) out.push(`${d(el)} ${Math.round(w)}x${Math.round(h)}`);
    }
    return out;
  }, describe.toString());
}

// One page in one state, four ways. `agent` puts the demo copy's agent in that state first; `login`
// opens the page without a session.
function scan(phase: string, route: string, opts: { agent?: AgentState; login?: boolean } = {}) {
  for (const [vp, size] of Object.entries(VIEWPORTS)) {
    for (const scheme of SCHEMES) {
      const name = `${phase} ${route} ${vp} ${scheme}`;
      test(name, async ({ page: shared, browser }) => {
        const ctx = opts.login ? await browser.newContext({ baseURL: BASE, storageState: { cookies: [], origins: [] } }) : null;
        const page = ctx ? await ctx.newPage() : shared;
        await page.setViewportSize(size);
        if (opts.agent) await agentTo(page, opts.agent);
        await open(page, route, scheme);
        const axe = await new AxeBuilder({ page }).withTags(TAGS).analyze();
        const violations = axe.violations.map((v) => ({
          id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.length,
          targets: v.nodes.slice(0, 5).map((n) => n.target.join(" ")),
        }));
        const focus = await focusGaps(page);
        const targets = vp === "phone" ? await smallTargets(page) : [];
        save(name, { route, variant: `${phase} ${vp} ${scheme}`, axe: violations, focus, targets });
        await ctx?.close();
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
    // The write lands a moment after the page went idle (the pages poll every 2 s): ask again for up to 5 s.
    let ok = false;
    for (let i = 0; i < 10 && !(ok = await done()); i++) await page.waitForTimeout(500);
    if (problems.length === 0 && !ok)
      problems.push(`Enter on ${id} did not do it (no code field the keyboard reaches, or the request failed)`);
  }
  if (problems.length) {
    expect(await fallback(), `${id} by API`).toBe(true);
    save(`keyboard ${id}`, { route: page.url(), variant: "keyboard", axe: [], focus: [], targets: [], error: problems.join("; ") });
  }
  expect(problems, `keyboard-only ${id}`).toEqual([]);
}

const api = (page: Page, path: string, method = "GET", body?: object) =>
  page.evaluate(async ([p, m, c, b]) => {
    const r = await fetch(p, {
      method: m,
      headers: { "X-Approve-Code": c, accept: "application/json", ...(b ? { "content-type": "application/json" } : {}) },
      body: b ?? undefined,
    });
    return { ok: r.ok, body: await r.json().catch(() => null) };
  }, [path, method, CODE, body ? JSON.stringify(body) : null] as const);

const agentState = async (page: Page): Promise<AgentState> => (await api(page, "/api/agent")).body?.state;

// The agent's own side of pairing, as any third-party agent does it (docs/AGENTS.md): answer the code
// with a name and a P-256 key. The kitchen then sees the consent screen.
async function agentCalls(page: Page): Promise<boolean> {
  const account = (await api(page, "/api/account")).body?.id;
  const code = (await api(page, "/api/agent")).body?.pairing?.code;
  const { publicKey } = generateKeyPairSync("ec", { namedCurve: "P-256" });
  const r = await fetch(`${BASE}/agent/v1/k/${account}/pair`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ code, name: "Claude Code", publicJwk: publicKey.export({ format: "jwk" }) }),
  });
  return r.status === 202;
}

// Walk the demo copy's agent to `want` through the real routes: back to none, then forward.
async function agentTo(page: Page, want: AgentState) {
  if (page.url() === "about:blank") await page.goto("/rules"); // a page of the app, for fetch with the session
  const now = await agentState(page);
  if (now === want) return;
  if (now === "active" || now === "paused") await api(page, "/api/agent/disconnect", "POST");
  else if (now === "pairing" || now === "consent") await api(page, "/api/agent/deny", "POST");
  const steps: [AgentState, () => Promise<unknown>][] = [
    ["pairing", () => api(page, "/api/agent/pair", "POST")],
    ["consent", () => agentCalls(page)],
    ["active", () => api(page, "/api/agent/allow", "POST")],
    ["paused", () => api(page, "/api/agent/pause", "POST", { paused: true })],
  ];
  for (const [state, step] of steps) {
    if (STATES.indexOf(want) < STATES.indexOf(state)) break;
    await step();
  }
  expect(await agentState(page), `agent ${want}`).toBe(want);
}

for (const route of PAGES) scan("before", route, { agent: "none" });
scan("before", "/login", { login: true });

test("keyboard: approve R-2 with the code on the phone", async ({ page }) => {
  await page.setViewportSize(VIEWPORTS.phone);
  await open(page, "/activity/R-2", "light");
  const o2 = async () => (await api(page, "/api/orders/O-2")).body?.state;
  await keyboard(page, "approve", async () => (await o2()) === "placed",
    async () => (await api(page, "/api/orders/O-2/approve", "POST")).ok);
});
scan("after", "/activity/R-2");

test("keyboard: connect an agent", async ({ page }) => {
  await page.setViewportSize(VIEWPORTS.desktop);
  await agentTo(page, "none");
  await open(page, "/agent", "light");
  await keyboard(page, "agent-connect", async () => (await agentState(page)) === "pairing",
    async () => (await api(page, "/api/agent/pair", "POST")).ok);
});

for (const state of STATES) scan(`agent ${state}`, "/agent", { agent: state });

test("keyboard: allow the agent", async ({ page }) => {
  await page.setViewportSize(VIEWPORTS.desktop);
  await agentTo(page, "consent");
  await open(page, "/agent", "light");
  await keyboard(page, "consent-allow", async () => (await agentState(page)) === "active",
    async () => (await api(page, "/api/agent/allow", "POST")).ok);
});

scan("agent active", "/", { agent: "active" });
