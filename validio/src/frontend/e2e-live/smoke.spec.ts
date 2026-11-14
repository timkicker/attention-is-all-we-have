import { CODE, agent, expect, fresh, pairAgent, stockOut, test } from "./kitchen";

// The built web app and the API from one process, no Vite: the login page lets a juror into a demo copy,
// the kitchen's agent (paired through the Agent page) places requests over MCP on the copy's own path,
// the pages read them through /api on the same origin.

test.describe.configure({ mode: "serial" });

test("app and API from one process, every page behind the login", async ({ browser, baseURL }) => {
  const anon = await browser.newContext({ baseURL });
  const r = anon.request;
  expect((await r.get("/api/health")).status()).toBe(200);
  expect((await r.get("/api/nope")).status()).toBe(404);
  expect((await r.get("/api/account")).status()).toBe(401);
  // a deep link is the SPA's index.html, not a 404, and the SPA sends a visitor to the login page
  const deep = await r.get("/requests/R-9");
  expect(deep.status()).toBe(200);
  expect(await deep.text()).toContain("<html");
  const p = await anon.newPage();
  await p.goto("/requests/R-9");
  await expect(p).toHaveURL(/\/login$/);
  await expect(p.getByTestId("try-demo")).toBeVisible();
  await anon.close();
});

test("the paired agent orders alone, the request opens from Orders", async ({ page, kitchen }) => {
  await fresh(kitchen);
  await pairAgent(kitchen, page);
  agent(kitchen, 2);
  await page.goto("/");
  await expect(page.getByTestId("demo-bar")).toContainText("Demo kitchen");
  await expect(page.locator("#inbox-R-1")).toHaveCount(0); // handled: in Orders, not the Inbox
  await page.getByTestId("nav-orders").click();
  await page.getByTestId("order-r-R-1").click();
  await expect(page).toHaveURL(/\/requests\/R-1$/);
  await expect(page.locator("#request-status")).toContainText("Ordered alone");
  await expect(page.locator("#live-checked")).toContainText("Live");
  await expect(page.locator("#option-464306")).toContainText("1,010.00");
  await expect(page.locator("#option-462921")).toContainText("hard cap");
  await page.reload(); // served by FastAPI's fallback
  await expect(page.locator("#request-status")).toContainText("Ordered alone");
});

test("owner approves the swap on the phone", async ({ page, kitchen }) => {
  // The stock-out has no control in the app or the API: set in the copy's store.
  stockOut(kitchen);
  await page.goto("/");
  await expect.poll(async () => (await (await page.request.get("/api/demo")).json()).stockOut466375).toBe(true);
  agent(kitchen, 3);
  await page.reload();
  await expect(page.locator("#inbox-R-2")).toContainText("Waiting for you");
  await page.locator("#inbox-R-2").click();
  await expect(page.locator("#option-473986")).toContainText("Not deliverable");
  await expect(page.locator("#option-465256")).toContainText("180.10");

  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByTestId("open-approve").click();
  await page.getByTestId("approve").click();
  // a demo copy asks its code (the demo bar names it) unless it was typed this visit
  if (await page.getByTestId("code-input").isVisible({ timeout: 2000 }).catch(() => false)) {
    await page.getByTestId("code-input").fill(CODE);
    await page.getByTestId("code-submit").click();
  }
  await expect(page.locator("#order-done")).toContainText("confirmed again");

  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/");
  await page.getByTestId("nav-ledger").click();
  await expect(page.locator("#chain-status")).toContainText("Verified");
  await expect(page.locator("#ledger")).toContainText("after the owner approved");
});

test("Reset in the demo bar starts the copy again", async ({ page }) => {
  // a demo copy goes back to the template: the example orders R-1 and R-2, nothing waiting, nothing newer
  const ids = async () =>
    ((await (await page.request.get("/api/inbox")).json()) as { id: string }[]).map((r) => r.id).sort();
  await page.goto("/");
  await page.getByTestId("demo-reset").click();
  await expect.poll(ids).toEqual(["R-1", "R-2"]);
  await page.goto("/");
  await expect(page.getByText("Nothing waits for you")).toBeVisible();
});
