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

test("ask as the kitchen's agent: one row per ask, the log folded", async ({ page }) => {
  await page.goto("/");
  await page.locator("#page-menu").click();
  await page.getByTestId("menu-ask").click();
  const dialog = page.getByTestId("ask-dialog");
  const log = page.getByTestId("ask-log");
  // One chip for each ending, each recorded at Valio; a tap sends it, rows stack newest on top.
  const cases = [
    { chip: "100 l whipping cream", pill: "Ordered alone", sub: null, end: true },
    { chip: "50 kg quark, budget 100 €", pill: "Waiting for you", sub: /^Over\sthe\s100\.00\s€\sbudget$/, end: true },
    { chip: "20 kg parmesan", pill: "Blocked", sub: /^Valio\shas\sno\slactose.free\sparmesan\.$/, end: false },
  ];
  for (const [i, c] of cases.entries()) {
    await page.locator(`#ask-chip-${i + 1}`).click();
    const row = page.getByTestId(`ask-row-R-${i + 1}`);
    await expect(row).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("ask-entry").first()).toContainText(c.pill);
    await expect(row).toContainText(c.pill);
    await expect(row).toHaveAttribute("href", `/requests/R-${i + 1}`);
    // The pill sits above the title, and the row is flush with the input.
    const pill = (await row.locator(".v-pill").boundingBox())!;
    const title = (await row.locator(".v-row-title").boundingBox())!;
    expect(pill.y + pill.height).toBeLessThanOrEqual(title.y + 1);
    const input = (await page.getByTestId("ask-input").boundingBox())!;
    expect(Math.abs(pill.x - input.x)).toBeLessThanOrEqual(1);
    const text = await row.innerText();
    expect(text).not.toMatch(/Open R-|Recorded at Valio|Agent asked/);
    if (c.end) expect(text).toMatch(/\d+\.\d\d\s€/);
    else expect(text).not.toMatch(/€/);
    if (c.sub) await expect(row.locator(".v-row-sub")).toHaveText(c.sub);
    await expect(page.getByTestId("ask-input")).toHaveValue("");
  }
  await expect(page.getByTestId("ask-entry")).toHaveCount(3);
  // The log is there, folded; nothing of it shows until opened, and no JSON when it is.
  await expect(log).not.toHaveAttribute("open", "");
  expect(await dialog.innerText()).not.toContain("request_supply");
  await log.locator("summary").click();
  // Only the latest ask (parmesan), plain steps, no code names.
  await expect(log).toContainText("Asks Validio");
  await expect(log).toContainText("parmesan");
  const steps = await log.innerText();
  expect(steps).not.toMatch(/[{}"→]|\b\d{6}\b|request_supply|whipping|quark/);
  const items = await log.locator("li").allInnerTexts();
  expect(new Set(items).size).toBe(items.length);

  // No request: one muted line, typed and sent with Enter.
  await page.getByTestId("ask-input").fill("30 litres of yoghurt by Monday");
  await page.getByTestId("ask-input").press("Enter");
  await expect(page.getByTestId("ask-none")).toHaveText(/^Not\srecorded\sfor\sthis\sdemo:\syoghurt$/, { timeout: 60_000 });
  expect(await dialog.innerText()).not.toContain("503");

  // The inbox says it as short.
  await page.getByTestId("ask-dialog").getByRole("button", { name: "Close" }).click();
  await expect(page.getByTestId("inbox-summary-R-2")).toHaveText(/^Over\sthe\s100\.00\s€\sbudget$/);
  await page.locator("#page-menu").click();
  await page.getByTestId("menu-ask").click();
  await page.getByTestId("ask-input").fill("20 kg of parmesan by Monday");
  await page.getByTestId("ask-input").press("Enter");
  await expect(page.getByTestId("ask-row-R-4")).toBeVisible({ timeout: 60_000 });
  // A row is one link to its request.
  await page.getByTestId("ask-row-R-1").click();
  await expect(page).toHaveURL(/\/requests\/R-1$/);
  await expect(page.locator("#request-status")).toContainText("Ordered alone");
  await expect(dialog).toHaveCount(0);
});

test("approving a blocked request: a plain state, not an outage", async ({ page }) => {
  // R-3 is the parmesan ask above: blocked, so there is no order to approve.
  const r = await (await page.request.get("/api/requests/R-3")).json();
  expect(r.status).toBe("blocked");
  await page.goto("/approve/R-3");
  await expect(page.getByTestId("approve-none")).toHaveText(/^Blocked\.\sNothing\sto\sapprove\.$/);
  await expect(page.locator("main")).not.toContainText("not reachable");
  await expect(page.getByRole("alert")).toHaveCount(0);
  await page.getByTestId("approve-none-request").click();
  await expect(page).toHaveURL(/\/requests\/R-3$/);
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
  await expect(page.getByTestId("f-auto-problem")).toHaveText("Must be below never above.");

  await page.getByTestId("f-hard").fill("2000");
  await page.getByTestId("f-code").fill(WRONG);
  await page.getByTestId("limits-save").click();
  await expect(page.getByTestId("f-code-problem")).toContainText("not right");

  await page.getByTestId("f-code").fill(CODE);
  await page.getByTestId("limits-save").click();
  await expect(page.getByTestId("limits-form")).toHaveCount(0);
  await expect(page.locator("main")).toContainText("1,300.00");
  await page.goto("/");
  await expect(page.getByTestId("pass-auto")).toHaveText(/^1,300\.00\s€$/);
  // The ledger: one group head "Spend Pass M-1", the entry names what changed.
  await page.goto("/ledger");
  await expect(page.getByTestId("ledger-group-M-1")).toHaveText(/^Spend\sPass\s*M-1$/);
  await expect(page.getByTestId("ledger")).toContainText(/Alone\sup\sto\s1,200\.00\s€\s→\s1,300\.00\s€/);
});

test("the stock-out switch turns on and off", async ({ page, request }) => {
  await page.goto("/");
  await page.locator("#page-menu").click();
  await page.getByTestId("stock-out").click();
  await expect.poll(async () => (await (await request.get("/api/demo")).json()).stockOut466375).toBe(true);
  await page.locator("#page-menu").click();
  await expect(page.getByTestId("stock-out")).toHaveAttribute("aria-checked", "true");
  await page.getByTestId("stock-out").click();
  await expect.poll(async () => (await (await request.get("/api/demo")).json()).stockOut466375).toBe(false);
  await page.locator("#page-menu").click();
  await expect(page.getByTestId("stock-out")).toHaveAttribute("aria-checked", "false");
  await page.keyboard.press("Escape");
  // Both switches are entries of the Demo group, which shows no id.
  await page.goto("/ledger");
  await expect(page.getByTestId("ledger-group-demo")).toHaveText(/^Demo$/);
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
