import { test, expect } from "@playwright/test";

// The play controls against the live backend: ask, change limits, stock-out on and off, and a
// refused Steady click that reloads the order.
const CODE = process.env.E2E_CODE!;
const WRONG = CODE === "000000" ? "111111" : "000000";

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  expect((await request.post("/api/demo/reset")).status()).toBe(200);
});
test.afterAll(async ({ request }) => {
  await request.post("/api/demo/reset");
});

test("ask as the kitchen's agent", async ({ page }) => {
  await page.goto("/");
  const ask = async (text: string) => {
    await page.locator("#page-menu").click();
    await page.getByTestId("menu-ask").click();
    await page.getByTestId("ask-input").fill(text);
    await page.getByTestId("ask-send").click();
  };
  await ask("20 kg of parmesan by Monday");
  await expect(page.getByTestId("ask-final")).toContainText("Validio could not take the request", { timeout: 60_000 });
  await expect(page.getByTestId("ask-lines")).toContainText("no recorded");
  await expect(page.getByTestId("ask-open")).toHaveCount(0);
  await page.getByRole("button", { name: "Close" }).click();

  await ask("500 litres of lactose-free milk by Monday");
  await expect(page.getByTestId("ask-open")).toBeVisible({ timeout: 60_000 });
  if (process.env.SHOTS) await page.screenshot({ path: `${process.env.SHOTS}/play-ask-live-1280-light.png` });
  await page.getByTestId("ask-open").click();
  await expect(page).toHaveURL(/\/requests\/R-\d+$/);
  await expect(page.locator("#request-status")).toBeVisible();
});

test("change limits: 422 and 403 inline, then signed", async ({ page }) => {
  await page.goto("/spend-pass");
  await page.getByTestId("change-limits").click();
  await page.getByTestId("f-auto").fill("1300");
  await page.getByTestId("f-hard").fill("1200");
  await page.getByTestId("f-code").fill(CODE);
  await page.getByTestId("limits-save").click();
  await expect(page.getByTestId("limits-problem")).toContainText("above never above");

  await page.getByTestId("f-hard").fill("2000");
  await page.getByTestId("f-code").fill(WRONG);
  await page.getByTestId("limits-save").click();
  await expect(page.getByTestId("limits-problem")).toContainText("not right");

  await page.getByTestId("f-code").fill(CODE);
  await page.getByTestId("limits-save").click();
  await expect(page.getByTestId("limits-form")).toHaveCount(0);
  await expect(page.locator("main")).toContainText("1,300.00");
  await page.goto("/");
  await expect(page.getByTestId("pass-auto")).toHaveText(/^1,300\.00\s€$/);
});

test("the stock-out switch turns on and off", async ({ page, request }) => {
  await page.goto("/");
  await page.locator("#page-menu").click();
  await page.getByTestId("stock-out").click();
  await expect.poll(async () => (await (await request.get("/api/demo")).json()).stockOut466375).toBe(true);
  await page.locator("#page-menu").click();
  await page.getByTestId("stock-back").click();
  await expect.poll(async () => (await (await request.get("/api/demo")).json()).stockOut466375).toBe(false);
  await page.locator("#page-menu").click();
  await expect(page.getByTestId("stock-out")).toBeVisible();
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
