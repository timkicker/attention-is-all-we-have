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

test("ask as the kitchen's agent: a short summary, the log folded", async ({ page }) => {
  await page.goto("/");
  const open = async () => {
    await page.locator("#page-menu").click();
    await page.getByTestId("menu-ask").click();
  };
  const summary = page.getByTestId("ask-summary");
  const log = page.getByTestId("ask-log");
  // One example chip for each ending, each recorded at Valio.
  const cases = [
    { chip: "100 litres of whipping cream by Monday", first: "Ordered alone: ", status: "Ordered alone" },
    { chip: "50 bags of lactose-free mozzarella by Monday", first: "Waits for you: ", status: "Waiting for you" },
    { chip: "20 kg of butter by Monday", first: "Blocked: ", status: "Blocked" },
  ];
  for (const [i, c] of cases.entries()) {
    await open();
    await page.getByRole("button", { name: c.chip, exact: true }).click();
    await expect(page.getByTestId("ask-input")).toHaveValue(c.chip);
    await page.getByTestId("ask-send").click();
    await expect(page.getByTestId("ask-open")).toBeVisible({ timeout: 60_000 });
    const lines = summary.locator("li");
    await expect(lines).toHaveCount(3);
    await expect(lines.nth(0)).toHaveText(/^Agent\sasked\sValidio\sfor\s.+\sby\s.+\.$/);
    await expect(lines.nth(1)).toHaveText(/^Checked\s\d+\sproducts\slive\.$/);
    await expect(lines.nth(2)).toHaveText(new RegExp(`^${c.first}`));
    // The raw log is there, folded; nothing of it shows until opened.
    await expect(log).not.toHaveAttribute("open", "");
    expect(await page.getByTestId("ask-dialog").innerText()).not.toContain("request_supply");
    await log.locator("summary").click();
    await expect(log).toContainText("request_supply");
    if (process.env.SHOTS && i === 0) {
      await log.locator("summary").click();
      await page.screenshot({ path: `${process.env.SHOTS}/play-ask-live-1280-light.png` });
    }
    await page.getByTestId("ask-open").click();
    await expect(page).toHaveURL(new RegExp(`/requests/R-${i + 1}$`));
    await expect(page.locator("#request-status")).toContainText(c.status);
  }

  // No request: the agent's last sentence is the one line.
  await open();
  await page.getByTestId("ask-input").fill("20 kg of saffron by Monday");
  await page.getByTestId("ask-send").click();
  await expect(summary.locator("li")).toHaveCount(1, { timeout: 60_000 });
  await expect(summary).toHaveText(/^Validio\scould\snot\stake\sthe\srequest,\snothing\sordered\.$/);
  await expect(page.getByTestId("ask-open")).toHaveCount(0);
  expect(await page.getByTestId("ask-dialog").innerText()).not.toContain("503");
});

test("change limits: 422 and 403 inline, then signed", async ({ page, request }) => {
  // The split limit is the seeded pass's, read from the API (500 basis points).
  const pass = await (await request.get("/api/spend-passes/M-1")).json();
  expect(pass.split.maxExtraCostPct).toBe(5);
  await page.goto("/spend-pass");
  await expect(page.locator("main")).toContainText(/up\sto\s5\s%\sextra/);
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
