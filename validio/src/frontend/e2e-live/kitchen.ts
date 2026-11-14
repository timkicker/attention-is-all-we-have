import { execFile, execFileSync } from "node:child_process";
import { test as base, expect, type BrowserContext, type Page } from "@playwright/test";

// The live e2e works on a demo copy, as a juror does: one browser context per worker logs in through the
// login page ("Try the demo kitchen"), and every test's page and API calls share its session. Each file
// starts that copy from the plain seed (POST /api/demo/reset {"fresh": true}: no template, no agent), so the
// ids of docs/DEMO.md hold on this machine and on the public link alike (E2E_BASE).
//
// The kitchen's agent is scripts/agent.py with --kitchen: paired through the Agent page's code with its own
// key, then MCP on /mcp/k/{account}/ of the same base.

/** A demo copy's approval code (api/accounts.DEMO_CODE); the demo bar names it. */
export const CODE = "246810";

type Kitchen = { ctx: BrowserContext; id: string; base: string };

export const test = base.extend<object, { kitchen: Kitchen }>({
  kitchen: [
    async ({ browser }, use, info) => {
      const baseURL = info.project.use.baseURL!;
      const ctx = await browser.newContext({ baseURL, viewport: { width: 1280, height: 900 } });
      const p = await ctx.newPage();
      await p.goto("/");
      await expect(p).toHaveURL(/\/login$/);
      await p.getByTestId("try-demo").click();
      await expect(p).not.toHaveURL(/\/login/);
      const acct = await (await ctx.request.get("/api/account")).json();
      expect(acct.isDemo).toBe(true);
      await p.close();
      await use({ ctx, id: acct.id, base: baseURL });
      await ctx.close();
    },
    { scope: "worker" },
  ],
  page: async ({ kitchen }, use) => {
    const p = await kitchen.ctx.newPage();
    await use(p);
    await p.close();
  },
  request: async ({ kitchen }, use) => {
    await use(kitchen.ctx.request);
  },
});
export { expect };

/** The demo copy back to the plain seed, no agent connected. */
export async function fresh(k: Kitchen) {
  const r = await k.ctx.request.post("/api/demo/reset", { data: { fresh: true } });
  expect(r.status(), await r.text()).toBe(200);
}

const cli = (k: Kitchen, args: string[]) =>
  ["run", "python", "-W", "ignore", "../../scripts/agent.py", "--base", k.base, "--kitchen", k.id, ...args];

/** The kitchen's agent plays one scene of docs/DEMO.md on this copy. */
export function agent(k: Kitchen, scene: number) {
  execFileSync("uv", cli(k, ["--scene", String(scene)]), { cwd: "../backend", env: process.env, stdio: "pipe" });
}

/** Connect the CLI agent the way a person does: Connect agent, the agent sends the code, Allow on the page. */
export async function pairAgent(k: Kitchen, page: Page) {
  await page.goto("/agent");
  await page.getByTestId("agent-connect").click();
  const code = (await page.getByTestId("pair-code").innerText()).trim();
  const done = new Promise<void>((ok, fail) =>
    execFile("uv", cli(k, ["--pair", code, "--wait", "60"]), { cwd: "../backend", env: process.env }, (err, _o, e) =>
      err ? fail(new Error(`agent.py --pair: ${e || err.message}`)) : ok()),
  );
  await page.getByTestId("consent-allow").click({ timeout: 60_000 });
  await done;
  await expect(page.getByTestId("agent-state")).toHaveText(/active/i);
}

/** The server's own demo agent, as "Connect the demo agent" and Allow do (the menu's Ask uses it). */
export async function connectDemoAgent(k: Kitchen) {
  expect((await k.ctx.request.post("/api/agent/demo")).status()).toBe(200);
  expect((await k.ctx.request.post("/api/agent/allow")).status()).toBe(200);
}
