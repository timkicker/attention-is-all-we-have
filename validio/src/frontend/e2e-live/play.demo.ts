import { CODE, connectMcpAgent, expect, fresh, test } from "./kitchen";

// The owner's controls against the live backend: change limits, and a refused Steady click that reloads
// the order. On a demo copy from the plain seed with an MCP agent connected (scripts/connector_check.py).
const WRONG = CODE === "000000" ? "111111" : "000000";

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ kitchen }) => {
  await fresh(kitchen);
  await connectMcpAgent(kitchen);
});
test.afterAll(async ({ kitchen }) => {
  await fresh(kitchen);
});

test("rules: 422 and 403 inline, then signed", async ({ page }) => {
  await page.goto("/agent");
  await page.getByTestId("rules-edit").click();
  await page.getByTestId("r-alone").fill("6000");
  await page.getByTestId("code-input").fill(CODE);
  await page.getByTestId("code-submit").click();
  await expect(page.locator("#r-alone-problem")).toHaveText("Above needs approval.");

  await page.getByTestId("r-alone").fill("1300");
  await page.getByTestId("code-input").fill(WRONG);
  await page.getByTestId("code-submit").click();
  await expect(page.locator("#code-help")).toContainText("not right");

  await page.getByTestId("code-input").fill(CODE);
  await page.getByTestId("code-submit").click();
  await expect(page.getByTestId("rules-form")).toHaveCount(0);
  await expect(page.getByTestId("rules-alone")).toContainText("1,300.00");
  await page.goto("/");
  await expect(page.getByTestId("pass-auto")).toHaveText(/^1,300\.00\s€$/);
});

test("a refused Steady click reloads the order", async ({ page }) => {
  await page.goto("/steady/S-1");
  await expect(page.locator("#renew")).toBeVisible();
  await page.route("**/api/steady/S-1/renew", (r) =>
    r.fulfill({ status: 409, contentType: "application/json", body: JSON.stringify({ detail: "the order changed meanwhile" }) }),
  );
  // the approval code is asked first, then the write is refused
  await page.locator("#renew").click();
  if (await page.getByTestId("code-input").isVisible({ timeout: 2000 }).catch(() => false)) {
    await page.getByTestId("code-input").fill(CODE);
    const reload = page.waitForRequest((q) => q.method() === "GET" && /\/api\/steady\/S-1$/.test(q.url()), { timeout: 1500 });
    await page.getByTestId("code-submit").click();
    await reload;
  } else {
    await page.waitForRequest((q) => q.method() === "GET" && /\/api\/steady\/S-1$/.test(q.url()), { timeout: 1500 });
  }
  await expect(page.getByRole("alert")).toContainText("changed meanwhile");
});
