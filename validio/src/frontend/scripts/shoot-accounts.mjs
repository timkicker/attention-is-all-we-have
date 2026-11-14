// Screenshots of every account screen state at 1280 and 390, light and dark, for a review round.
//
//   node scripts/shoot-accounts.mjs <out-dir> [--base http://127.0.0.1:8410]
//
// Without --base it builds the web app (VITE_API=live), plays the demo template into a temporary
// directory and starts its own server on a free port from replayed Valio answers; nothing under data/
// is touched. Each view gets a fresh browser, so a fresh demo copy, and walks the "Done means" path,
// shooting each state as <out-dir>/<nn>-<state>-<width>-<theme>.png. A control the pages do not have
// yet is listed as missing and the walk goes on; SHOOT_STRICT=1 makes that fail the run.
import { spawn, spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { chromium } from "@playwright/test";

const args = process.argv.slice(2);
const OUT = args.find((a, i) => !a.startsWith("--") && args[i - 1] !== "--base");
if (!OUT) {
  console.error("usage: node scripts/shoot-accounts.mjs <out-dir> [--base URL]");
  process.exit(2);
}
let BASE = args.includes("--base") ? args[args.indexOf("--base") + 1].replace(/\/$/, "") : null;
const STRICT = process.env.SHOOT_STRICT === "1";
const CODE = "246810";
const FRONT = resolve(import.meta.dirname, "..");
const BACK = resolve(FRONT, "../backend");
const VIEWS = [
  { width: 1280, height: 900, theme: "light" },
  { width: 1280, height: 900, theme: "dark" },
  { width: 390, height: 844, theme: "light" },
  { width: 390, height: 844, theme: "dark" },
];
const missing = new Set();
const shots = [];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function run(cmd, argv, cwd, env = {}) {
  const r = spawnSync(cmd, argv, { cwd, env: { ...process.env, ...env }, stdio: "inherit" });
  if (r.status !== 0) throw new Error(`${cmd} ${argv.join(" ")} failed`);
}

const freePort = () =>
  new Promise((ok) => {
    const s = createServer().listen(0, "127.0.0.1", () => {
      const { port } = s.address();
      s.close(() => ok(port));
    });
  });

async function startServer() {
  run("npm", ["run", "build"], FRONT, { VITE_API: "live" });
  const tmp = mkdtempSync(join(tmpdir(), "shoot-accounts-"));
  const env = { GEMINI_API_KEY: "", VALIO_MODE: "replay", VALIDIO_DEMO: "1", VALIDIO_DEMO_TOKEN: "",
    VALIDIO_APPROVE_CODE: CODE, VALIDIO_PUBLIC: "", VALIDIO_PUBLIC_READ: "", VALIDIO_KITCHEN_TOKEN: "",
    VALIDIO_DB: join(tmp, "local/validio.db"), VALIDIO_KEYS: join(tmp, "local/keys"),
    VALIDIO_ACCOUNTS: join(tmp, "accounts"), VALIDIO_TEMPLATE: join(tmp, "template") };
  mkdirSync(join(tmp, "local"), { recursive: true });
  // the flags `make template` uses, so the shots start from the template the deploy builds
  const m = readFileSync(resolve(FRONT, "../../Makefile"), "utf8").match(/^template:\n\t.*demo_check\.py (.*?)--store/m);
  if (!m) throw new Error("the Makefile has no template target calling demo_check.py --store");
  run("uv", ["run", "python", "-W", "ignore", "../../scripts/demo_check.py", ...m[1].trim().split(/\s+/), "--store", env.VALIDIO_TEMPLATE], BACK, env);
  run("uv", ["run", "python", "../../scripts/seed_demo.py"], BACK, env);
  const port = await freePort();
  const proc = spawn("uv", ["run", "uvicorn", "validio.api.app:app", "--host", "127.0.0.1", "--port", String(port)],
    { cwd: BACK, env: { ...process.env, ...env }, stdio: "ignore" });
  const base = `http://127.0.0.1:${port}`;
  for (let i = 0; i < 150; i++) {
    try {
      if ((await fetch(`${base}/api/health`)).ok) return { base, stop: () => { proc.kill(); rmSync(tmp, { recursive: true, force: true }); } };
    } catch { /* not up yet */ }
    await sleep(200);
  }
  proc.kill();
  throw new Error("server did not start");
}

async function walk(browser, v) {
  const ctx = await browser.newContext({ baseURL: BASE, viewport: { width: v.width, height: v.height }, colorScheme: v.theme });
  await ctx.addInitScript((t) => { try { localStorage.setItem("validio-theme", t); } catch { /* none */ } }, v.theme);
  const page = await ctx.newPage();
  page.setDefaultTimeout(6000);
  let n = 0;
  const shoot = async (state) => {
    await page.waitForLoadState("networkidle").catch(() => {});
    await sleep(300);
    const file = `${String(++n).padStart(2, "0")}-${state}-${v.width}-${v.theme}.png`;
    await page.screenshot({ path: join(OUT, file), fullPage: true });
    shots.push(file);
  };
  // a control by test id, else by role and label; null (and listed) when the page has neither
  const find = async (state, id, role, name) => {
    const loc = page.getByTestId(id).or(page.getByRole(role, { name })).filter({ visible: true }).first();
    const there = await loc.waitFor({ timeout: 4000 }).then(() => true, () => false);
    if (!there) missing.add(`${state}: ${id} / ${role} ${name}`);
    return there ? loc : null;
  };
  const click = async (state, id, role, name) => {
    const loc = await find(state, id, role, name);
    if (loc) await loc.click();
    return !!loc;
  };
  // the code prompt: shot, typed when the page asks (a page that remembers it this visit does not), submitted
  const code = async (state) => {
    const box = page.getByTestId("code-input").filter({ visible: true }).first();
    const asks = await box.waitFor({ timeout: 3000 }).then(() => true, () => false);
    await shoot(`${state}-code`);
    if (!asks) return;
    await box.fill(CODE);
    await page.getByTestId("code-submit").filter({ visible: true }).first().click()
      .catch(() => missing.add(`${state}: code-submit`));
  };
  // A phone detail page (request, approve) has a back link and no dock: home first, as a person would.
  const home = async () => {
    const dock = page.getByTestId("nav-inbox").filter({ visible: true }).first();
    if (!(await dock.waitFor({ timeout: 1000 }).then(() => true, () => false))) await page.goto("/");
  };
  const nav = async (state, id, name) => {
    await home();
    return click(state, id, "link", name);
  };
  const example = async (state) => {
    await nav(state, "nav-inbox", /^inbox$/i);
    if (await click(state, "example-send", "button", /send example request/i)) await sleep(1500);
    await shoot(state);
  };

  // login, sign up, and a new account's empty inbox with the checklist
  await page.goto("/login");
  await shoot("login");
  if (await click("login", "login-submit", "button", /^log in$/i)) await shoot("login-problems");
  if (await click("signup", "login-swap", "button", /create account/i)) {
    await shoot("signup");
    const fill = (id, value) => page.getByTestId(id).fill(value).catch(() => missing.add(`signup: ${id}`));
    await fill("login-kitchen", "School kitchen");
    await fill("login-email", `shots-${Date.now()}-${v.width}${v.theme}@example.org`);
    await fill("login-password", "long enough");
    await fill("login-customer", "123456");
    await fill("login-code", "135790");
    await page.getByTestId("login-submit").click().catch(() => {});
    await page.waitForURL((u) => !u.pathname.startsWith("/login"), { timeout: 8000 }).catch(() => missing.add("signup: no app after submit"));
    await shoot("new-inbox-checklist");
    if (await nav("new-agent", "nav-agent", /^agent$/i)) await shoot("new-agent-none");
    await page.context().clearCookies();
    await page.evaluate(() => { for (const k of Object.keys(localStorage)) if (k !== "validio-theme") localStorage.removeItem(k); });
  }

  // the demo kitchen
  await page.goto("/login");
  if (!(await click("demo", "try-demo", "button", /try the demo kitchen/i))) return ctx.close();
  await page.waitForURL((u) => !u.pathname.startsWith("/login"), { timeout: 15000 }).catch(() => {});
  await shoot("inbox");
  if (await nav("orders", "nav-orders", /^orders$/i)) await shoot("orders");
  if (await click("menu", "page-menu", "button", /more|menu/i)) {
    await shoot("menu");
    await page.keyboard.press("Escape");
  }

  // agent: none, pairing, consent, active, technical fold
  if (await nav("agent", "nav-agent", /^agent$/i)) {
    await shoot("agent-none");
    if (await click("agent-pairing", "agent-connect", "button", /^connect agent$/i)) await shoot("agent-pairing");
    if (await click("agent-consent", "agent-demo", "button", /connect the demo agent/i)) await shoot("agent-consent");
    if (await click("agent-active", "consent-allow", "button", /^allow$/i)) await shoot("agent-active");
    const tech = page.getByTestId("tech-fold").locator("summary").filter({ visible: true }).first();
    if (await tech.count()) {
      await tech.click();
      await shoot("agent-technical");
      await tech.click();
    } else missing.add("agent-technical: tech-fold");
  }

  // the example request, ordered alone, and its page
  await example("inbox-ordered");
  const ordered = page.getByText(/ordered alone/i).filter({ visible: true }).first();
  if (await ordered.count()) {
    await ordered.click();
    await shoot("request-ordered");
  }

  // Rules: lower the alone limit, the code prompt, saved
  if (await nav("rules", "nav-agent", /^agent$/i)) {
    await page.locator("#rules").scrollIntoViewIfNeeded().catch(() => {});
    if (await click("rules", "rules-edit", "button", /^(edit|set rules)$/i)) {
      const alone = page.getByTestId("r-alone");
      if (await alone.fill("800").then(() => true, () => false)) {
        await code("rules");
        await shoot("rules-saved");
      } else missing.add("rules: r-alone");
    }
  }

  // the same request waits; its page; the approval page with the code
  await example("inbox-waiting");
  const waiting = page.getByText(/waiting for you/i).filter({ visible: true }).first();
  if (await waiting.count()) {
    await waiting.click();
    await shoot("request-waiting");
    if (await click("approve", "open-approve", "link", /open approval/i)) {
      await shoot("approve");
      if (await click("approve", "approve", "button", /^approve$/i)) {
        await code("approve");
        await shoot("approve-done");
      }
    }
  } else missing.add("inbox-waiting: no waiting request");

  // pause, the refusal, the ledger filtered to the agent
  if (await nav("paused", "nav-agent", /^agent$/i) && await click("paused", "agent-pause", "button", /^pause$/i)) {
    await shoot("agent-paused");
    await example("inbox-refused");
    await nav("ledger", "nav-agent", /^agent$/i);
    if (await click("ledger", "agent-ledger", "link", /see in ledger/i)) await shoot("ledger-agent");
  }
  if (await nav("ledger", "nav-ledger", /^ledger$/i)) await shoot("ledger");

  // Settings, the diet with its code prompt
  await home();
  const settings = page.getByTestId("nav-settings").or(page.getByTestId("phone-settings")).filter({ visible: true }).first();
  if (await settings.count()) {
    await settings.click();
    await shoot("settings");
    // one page with a section list on the side at 1280; on the phone one list, nothing to pick
    const sections = (await page.getByTestId(/^set-(nav|row)-/).filter({ visible: true }).count()) > 0;
    if (sections && (await click("settings-diet", /^set-(nav|row)-diet$/, "link", /diet and allergens/i))) await shoot("settings-diet");
    const gluten = page.getByRole("switch", { name: /gluten/i }).or(page.getByRole("checkbox", { name: /gluten/i })).filter({ visible: true }).first();
    if (await gluten.count()) {
      await gluten.click();
      if (await click("settings-diet", "diet-save", "button", /^save$/i)) {
        await code("settings-diet");
        await shoot("settings-saved");
      }
    } else missing.add("settings: gluten switch");
    for (const [id, name] of sections ? [["kitchen", /^kitchen$/i], ["login", /login and approval code/i], ["theme", /^theme$/i]] : []) {
      await page.goto("/settings");
      if (!(await click(`settings-${id}`, new RegExp(`^set-(nav|row)-${id}$`), "link", name))) continue;
      await shoot(`settings-${id}`);
      if (id === "kitchen" && (await click("settings-kitchen-edit", "kitchen-edit", "button", /^edit$/i))) await shoot("settings-kitchen-edit");
    }
  } else missing.add("settings: nav-settings / phone-settings");
  await ctx.close();
}

let server = null;
mkdirSync(OUT, { recursive: true });
try {
  if (!BASE) {
    server = await startServer();
    BASE = server.base;
  }
  const browser = await chromium.launch();
  for (const v of VIEWS) {
    // one after another (CPU rule); a view that breaks is reported and the next one still runs
    await walk(browser, v).catch((e) => missing.add(`${v.width} ${v.theme}: stopped: ${String(e.message).split("\n")[0]}`));
  }
  await browser.close();
} finally {
  server?.stop();
}
console.log(`${shots.length} shots in ${resolve(OUT)}`);
if (missing.size) console.log(`missing (${missing.size}):\n  ${[...missing].join("\n  ")}`);
process.exit(STRICT && missing.size ? 1 : 0);
