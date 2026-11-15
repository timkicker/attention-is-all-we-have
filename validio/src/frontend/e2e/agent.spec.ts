import { test, expect, type Page } from "@playwright/test";
import { fresh, slop } from "./helpers";

// Agent page in fixture mode: the demo starts with no agent, as the real demo
// copy does. Connect, the code appearing by itself on the agent's first call
// (validioMcpCall plays it), Deny and Allow, then pause and disconnect.

const call = (page: Page) => page.evaluate(() => (window as unknown as { validioMcpCall: () => void }).validioMcpCall());

async function toAgent(page: Page, connect = true) {
  await fresh(page);
  await page.goto("/agent");
  await expect(page.locator("h1")).toHaveText("Agent");
  await expect(page.getByTestId("agent-none")).toBeVisible();
  if (!connect) return;
  await page.locator("#agent-connect").click();
  await expect(page.getByTestId("mcp-url")).toBeVisible();
  await call(page);
  await page.locator("#consent-allow").click();
  await expect(page.getByTestId("agent-state")).toHaveText("Active");
}

async function disconnect(page: Page) {
  await page.locator("#agent-disconnect").click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("It can no longer order.");
  await dialog.getByRole("button", { name: "Disconnect" }).click();
  await expect(page.getByTestId("agent-none")).toBeVisible();
}

async function noSideScroll(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);
}

test("a connected agent shows name, connected and last used, and links to its activity", async ({ page }) => {
  await toAgent(page);
  await expect(page.getByTestId("agent-name-value")).toHaveText("MCP agent");
  await expect(page.getByTestId("agent-connected-value")).toHaveText(/^\w{3}\s\d+\s\w{3},\s\d\d:\d\d$/);
  await expect(page.getByTestId("agent-used-value")).toHaveText("Not yet");
  expect(await slop(page)).toEqual([]);
  await page.getByTestId("agent-activity").click();
  await expect(page).toHaveURL(/\/activity$/);
});

test("pause and resume", async ({ page }) => {
  await toAgent(page);
  await page.locator("#agent-pause").click();
  await expect(page.getByTestId("agent-state")).toHaveText("Paused");
  await expect(page.locator("#agent-pause")).toHaveText("Resume");
  await page.reload();
  await expect(page.getByTestId("agent-state")).toHaveText("Paused");
  await page.locator("#agent-pause").click();
  await expect(page.getByTestId("agent-state")).toHaveText("Active");
});

test("disconnect asks first, and Cancel keeps the agent", async ({ page }) => {
  await toAgent(page);
  await page.locator("#agent-disconnect").click();
  await page.getByRole("dialog").getByRole("button", { name: "Cancel" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByTestId("agent-state")).toHaveText("Active");
  await disconnect(page);
  await expect(page.getByTestId("agent-state")).toHaveCount(0);
  await expect(page.locator("#agent-connect")).toHaveText("Connect agent");
});

test("connecting shows the MCP address, the fold for other agents, and Cancel", async ({ page }) => {
  await toAgent(page, false);
  await page.locator("#agent-connect").click();
  await expect(page.getByTestId("agent-state")).toHaveText("Connecting");
  await expect(page.getByTestId("mcp-hint")).toHaveText("Add this address to your agent as an MCP server, then ask it to order something.");
  await expect(page.getByTestId("mcp-url")).toContainText("/mcp/c/");
  // No vendor is named anywhere on the page.
  await expect(page.locator("body")).not.toContainText(/claude|anthropic|openai|chatgpt/i);
  await expect(page.getByTestId("pair-code-text")).toBeHidden();
  await page.locator("#agent-nomcp summary").click();
  await expect(page.getByTestId("pair-code-text")).toHaveText(/^[A-Z2-9]{4}-[A-Z2-9]{4}$/);
  await expect(page.locator("#pair-code")).toContainText(/Valid until \d\d:\d\d/);
  await expect(page.getByTestId("api-url")).toContainText("/agent/v1/k/");
  expect(await slop(page)).toEqual([]);
  await page.locator("#pair-cancel").click();
  await expect(page.getByTestId("agent-none")).toBeVisible();
});

test("the agent's first call shows the code without a reload; Deny, then Allow", async ({ page }) => {
  await toAgent(page, false);
  await page.locator("#agent-connect").click();
  await expect(page.getByTestId("mcp-url")).toBeVisible();
  await page.evaluate(() => (window as unknown as { validioMcpCall: () => void }).validioMcpCall());
  await expect(page.getByTestId("verify-code")).toHaveText(/^[A-Z2-9]{3}-[A-Z2-9]{3}$/, { timeout: 5000 });
  await expect(page.getByTestId("agent-state")).toHaveText("Check the code");
  await expect(page.getByTestId("consent-who")).toHaveText(/^MCP agent called at \d\d:\d\d$/);
  await expect(page.getByTestId("consent")).toContainText("Your agent shows this code too. Allow only if it matches.");
  await expect(page.getByTestId("consent-may")).toContainText("Auto-orders up to 1,200.00 €");
  expect(await slop(page)).toEqual([]);
  // The code is random and is read out letter by letter: a run that drew a unit code ("PSS") is still clean.
  await page.getByTestId("verify-code").evaluate((e) => (e.textContent = "PSS-EUR"));
  expect(await slop(page)).toEqual([]);
  await page.locator("#consent-deny").click();
  await expect(page.getByTestId("agent-none")).toBeVisible();

  await page.locator("#agent-connect").click();
  await expect(page.getByTestId("mcp-url")).toBeVisible();
  await page.evaluate(() => (window as unknown as { validioMcpCall: () => void }).validioMcpCall());
  await page.locator("#consent-allow").click();
  await expect(page.getByTestId("agent-state")).toHaveText("Active");
  await expect(page.getByTestId("agent-name-value")).toHaveText("MCP agent");
  await expect(page.getByTestId("agent-used-value")).toHaveText("Not yet");
});

test("every state fits a 390 px phone", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await toAgent(page);
  await noSideScroll(page);
  await disconnect(page);
  await noSideScroll(page);
  await page.locator("#agent-connect").click();
  await page.locator("#agent-nomcp summary").click();
  await expect(page.getByTestId("api-url")).toBeVisible();
  await noSideScroll(page);
  await page.evaluate(() => (window as unknown as { validioMcpCall: () => void }).validioMcpCall());
  await expect(page.getByTestId("verify-code")).toBeVisible({ timeout: 5000 });
  await noSideScroll(page);
});

test("with no agent, one line sends the person to their Rules first", async ({ page }) => {
  await toAgent(page, false);
  await expect(page.getByTestId("agent-none-rules")).toHaveText("Check your Rules first. Your agent orders within them.");
  await page.locator("#agent-rules-link").click();
  await expect(page).toHaveURL(/\/rules$/);
  await expect(page.locator("h1")).toHaveText("Rules");
});
