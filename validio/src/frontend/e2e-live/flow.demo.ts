import { connectMcp, connector, requested } from "./connector";
import { CODE, expect, fresh, test } from "./kitchen";

// The v2 key flow against the live backend, on a demo copy from the plain seed: a real MCP client
// (scripts/connector_check.py) connects through the Agent page, orders alone, then, after the owner
// lowers the limit in Rules, waits for the owner, who approves on the detail page. Pause refuses it,
// Disconnect ends the connector URL. Needs no local store: runs against E2E_BASE as well.

test.describe.configure({ mode: "serial" });

let url = "";
let second = "";

test.beforeAll(async ({ kitchen }) => {
  await fresh(kitchen);
});
test.afterAll(async ({ kitchen }) => {
  await fresh(kitchen);
});

test("connect: the code on the page is the code the client got, then Allow", async ({ page }) => {
  await page.goto("/agent");
  await expect(page.getByTestId("agent-none")).toBeVisible();
  url = await connectMcp(page);
  await expect(page.getByTestId("agent-name-value")).not.toBeEmpty();
});

test("the client orders 1,000 l lactose-free milk alone: Home Latest and Activity", async ({ page }) => {
  const run = connector(url);
  expect(run.ok, run.out).toBe(true);
  const r = requested(run.out);
  expect(r.outcome, run.out).toBe("auto_order");

  await page.goto("/");
  const row = page.getByTestId("section-latest").getByTestId(`activity-${r.id}`);
  await expect(row).toHaveAttribute("data-status", "ordered");
  await expect(row).toContainText("Ordered alone");
  await expect(row).toContainText(/milk/i);

  await page.getByTestId("nav-activity").click();
  await expect(page).toHaveURL(/\/activity$/);
  const a = page.getByTestId(`activity-${r.id}`);
  await expect(a).toContainText("Ordered alone");
  await a.click();
  await expect(page).toHaveURL(new RegExp(`/activity/${r.id}$`));
  await expect(page.getByTestId("detail-status")).toHaveText("Ordered alone");
  await expect(page.getByTestId("asked")).toContainText(/lactose-free milk/i);
  await expect(page.getByTestId("approval")).toHaveCount(0);
});

test("Rules: lower the alone limit (and room above it) with the code", async ({ page }) => {
  await page.goto("/rules");
  const before = Number(((await page.getByTestId("rules-version").textContent()) ?? "").match(/\d+/)?.[0]);
  await page.getByTestId("rules-edit").click();
  await expect(page).toHaveURL(/\/rules\/edit$/);
  await page.getByTestId("f-alone").fill("500");
  // The seed's hard cap counts what the pass already placed (1,010 €): room for a second 1,010 € order.
  await page.getByTestId("f-waiting").fill("5000");
  await expect(page.getByTestId("rules-changes")).not.toBeEmpty();
  await page.getByTestId("code-input").fill(CODE);
  await page.getByTestId("code-submit").click();
  await expect(page).toHaveURL(/\/rules\?saved$/);
  await expect(page.getByTestId("rules-version")).toContainText(`Version ${before + 1}`);
  const rules = await (await page.request.get("/api/rules")).json();
  expect(rules.aloneUpToCents).toBe(50000);
  expect(rules.approvalUpToCents).toBe(500000);
});

test("the same order now needs the owner: Home Needs you, Approve with the code", async ({ page }) => {
  const run = connector(url);
  expect(run.ok, run.out).toBe(true);
  const r = requested(run.out);
  expect(r.outcome, run.out).not.toBe("auto_order");
  second = r.id;

  await page.goto("/");
  await expect(page.getByTestId(`need-${second}`)).toBeVisible();
  await page.getByTestId(`review-${second}`).click();
  await expect(page).toHaveURL(new RegExp(`/activity/${second}$`));
  await expect(page.getByTestId("detail-status")).toHaveText("Waiting for you");
  await expect(page.getByTestId("result-none")).toHaveText("Not ordered yet");
  await page.getByTestId("approve").click();
  await page.getByTestId("code-input").fill(CODE);
  await page.getByTestId("code-submit").click();
  await expect(page.getByTestId("approval")).toHaveCount(0);
  await expect(page.getByTestId("result-order")).toBeVisible();

  await page.goto("/");
  await expect(page.getByTestId(`need-${second}`)).toHaveCount(0);
  await expect(page.getByTestId("needs-none")).toBeVisible();
});

test("Pause: the client is refused; Disconnect: the URL is gone", async ({ page, request }) => {
  await page.goto("/agent");
  await expect(page.getByTestId("agent-state")).toHaveText("Active");
  await page.getByTestId("agent-pause").click();
  await expect(page.getByTestId("agent-state")).toHaveText("Paused");
  const paused = connector(url);
  expect(paused.ok, paused.out).toBe(false);
  expect(paused.out).toMatch(/paus/i);

  await page.getByTestId("agent-disconnect").click();
  await page.getByRole("dialog").getByRole("button", { name: "Disconnect", exact: true }).click();
  await expect(page.getByTestId("agent-none")).toBeVisible();
  const gone = await request.post(url, {
    headers: { "content-type": "application/json", accept: "application/json, text/event-stream" },
    data: { jsonrpc: "2.0", id: 1, method: "initialize", params: {} },
  });
  expect(gone.status()).toBe(404);
});
