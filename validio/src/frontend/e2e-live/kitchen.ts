import { test as base, expect, type BrowserContext } from "@playwright/test";
import { connectMcp } from "./connector";

// The live e2e works on a demo copy, as a juror does: one browser context per worker logs in through the
// login page ("Try the demo kitchen"), and every test's page and API calls share its session. Each file
// starts that copy from the plain seed (POST /api/demo/reset {"fresh": true}: no template, no agent), so the
// ids of docs/DEMO.md hold on this machine and on the public link alike (E2E_BASE).
//
// The kitchen's agent is a real MCP client (scripts/connector_check.py) on the connector URL the Agent page
// shows (connector.ts).

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

/** The kitchen's agent as any MCP agent connects: the connector on the Agent page's URL, then Allow. */
export async function connectMcpAgent(k: Kitchen) {
  const page = await k.ctx.newPage();
  const url = await connectMcp(page);
  await page.close();
  return url;
}
