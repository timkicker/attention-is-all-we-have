import { spawnSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, type Page } from "@playwright/test";

// A real MCP agent on the Agent page's connector URL: scripts/connector_check.py, the python `mcp` client
// over streamable HTTP, run from src/backend. Its first call asks for consent (the agent gets the
// verification code in its tool answer); after Allow each run asks for 1000 l of lactose-free milk.

const BACKEND = resolve(dirname(fileURLToPath(import.meta.url)), "../../backend");
const CODE_RE = /\b[A-Z2-9]{3}-[A-Z2-9]{3}\b/;

/** One run of the connector against `url`: whether it ordered (exit 0) and what it printed. */
export function connector(url: string): { ok: boolean; out: string } {
  const r = spawnSync("uv", ["run", "python", "-W", "ignore", "../../scripts/connector_check.py", url], {
    cwd: BACKEND,
    env: process.env,
    encoding: "utf8",
    timeout: 90_000,
  });
  return { ok: r.status === 0, out: `${r.stdout ?? ""}${r.stderr ?? ""}` };
}

/** Connect agent on the Agent page, the connector's first call, the codes compared, Allow. Returns the URL. */
export async function connectMcp(page: Page): Promise<string> {
  await page.goto("/agent");
  await page.getByTestId("agent-connect").click();
  const url = ((await page.getByTestId("mcp-url").textContent()) ?? "").trim();
  expect(url).toMatch(/\/mcp\/c\/[^/]+\/$/);
  const first = connector(url);
  const code = page.getByTestId("verify-code");
  await expect(code).toHaveText(/^[A-Z2-9]{3}-[A-Z2-9]{3}$/, { timeout: 30_000 });
  // The agent was told the same code the page shows.
  expect(first.out.match(CODE_RE)?.[0], first.out).toBe((await code.textContent())?.trim());
  await page.getByTestId("consent-allow").click();
  await expect(page.getByTestId("agent-state")).toHaveText(/active/i);
  return url;
}

/** The request id and outcome the connector printed ("request_supply: R-3 auto_order: ..."). */
export function requested(out: string): { id: string; outcome: string } {
  const m = out.match(/request_supply: (\S+) (\w+):/);
  expect(m, out).toBeTruthy();
  return { id: m![1], outcome: m![2] };
}
