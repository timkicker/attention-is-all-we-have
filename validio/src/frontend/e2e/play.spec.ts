import { test, expect } from "@playwright/test";
import { CODE, fresh, stockOut } from "./helpers";

// The play controls against the fixture: ask, change limits, stock-out on and off.

test("ask without a backend says so calmly", async ({ page }) => {
  await fresh(page);
  await page.locator("#page-menu").click();
  await page.getByTestId("menu-ask").click();
  await expect(page.getByTestId("ask-send")).toBeDisabled();
  await page.getByTestId("ask-input").fill("500 litres of lactose-free milk by Monday");
  await page.getByTestId("ask-send").click();
  const summary = page.getByTestId("ask-summary");
  await expect(summary.locator("li")).toHaveCount(1);
  await expect(summary).toContainText("no backend");
  await expect(summary).not.toHaveClass(/bad/);
  await expect(page.getByTestId("ask-log")).toHaveCount(0);
  await expect(page.getByTestId("ask-open")).toHaveCount(0);
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("change limits: 422 inline, then the new numbers everywhere", async ({ page }) => {
  await fresh(page);
  await page.goto("/spend-pass");
  await page.getByTestId("change-limits").click();
  const form = page.getByTestId("limits-form");
  await expect(form).toContainText("Recorded for 16 Nov only.");
  await expect(page.locator("#f-lactose")).toBeChecked();
  await expect(page.locator("#f-deliver")).toHaveValue("2026-11-16");
  await page.getByTestId("f-auto").fill("1900");
  await page.getByTestId("f-hard").fill("1800");
  if (await page.getByTestId("f-code").isVisible()) await page.getByTestId("f-code").fill(CODE);
  await page.getByTestId("limits-save").click();
  await expect(page.getByTestId("limits-problem")).toContainText("above never above");

  await page.getByTestId("f-auto").fill("900");
  await page.getByTestId("limits-save").click();
  await expect(form).toHaveCount(0);
  await expect(page.locator("main")).toContainText("900.00");
  await page.goto("/");
  await expect(page.getByTestId("pass-auto")).toHaveText(/^900\.00\s€$/);
  await expect(page.getByTestId("pass-cap")).toHaveText(/^1,800\.00\s€$/);
});

test("the stock-out switch turns off again", async ({ page }) => {
  await fresh(page);
  await stockOut(page);
  await expect(page.getByTestId("inbox-R-2")).toBeVisible();
  await page.locator("#page-menu").click();
  await expect(page.getByTestId("stock-out")).toHaveCount(0);
  await page.getByTestId("stock-back").click();
  await page.locator("#page-menu").click();
  await expect(page.getByTestId("stock-out")).toBeEnabled();
  await expect(page.getByTestId("stock-back")).toHaveCount(0);
  await page.keyboard.press("Escape");
  // What the agent already asked for stays where it was.
  await expect(page.getByTestId("inbox-R-2")).toBeVisible();
});

// The public link: every write needs the presenter's token. The first write asks for it once,
// a wrong one asks again, then the write runs; later writes send it without asking.
test("on the public link every write asks for the demo token once", async ({ page }) => {
  await fresh(page);
  await page.evaluate(() => localStorage.setItem("validio-mock-public", "pub-token"));
  await page.goto("/steady/S-1");
  await page.getByTestId("renew").click();
  if (await page.getByTestId("code-input").isVisible({ timeout: 2000 }).catch(() => false)) {
    await page.getByTestId("code-input").fill(CODE);
    await page.getByTestId("code-submit").click();
  }
  const token = page.locator("#demo-token-input");
  await expect(token).toBeVisible();
  await token.fill("wrong");
  await page.getByRole("button", { name: "Use and run" }).click();
  await expect(page.getByText("That token is not right.")).toBeVisible();
  await token.fill("pub-token");
  await page.getByRole("button", { name: "Use and run" }).click();
  await expect(page.getByTestId("line-463968")).toContainText("772.49");

  // The same page session (the token lives in memory): the stock-out switch and approve send it without asking.
  await page.locator("#nav-inbox").click();
  await page.locator("#page-menu").click();
  await page.getByTestId("stock-out").click();
  await expect(page.getByTestId("inbox-R-2")).toBeVisible();
  await expect(token).toHaveCount(0);
  await page.getByTestId("inbox-R-2").click();
  await page.locator("#open-approve").click();
  await page.getByTestId("approve").click();
  if (await page.getByTestId("code-input").isVisible({ timeout: 2000 }).catch(() => false)) {
    await page.getByTestId("code-input").fill(CODE);
    await page.getByTestId("code-submit").click();
  }
  await expect(page.locator("#order-done")).toBeVisible();
  await expect(token).toHaveCount(0);
});

test("closing the token dialog sends nothing and shows no error", async ({ page }) => {
  await fresh(page);
  await page.evaluate(() => localStorage.setItem("validio-mock-public", "pub-token"));
  await page.locator("#page-menu").click();
  await page.getByTestId("stock-out").click();
  await expect(page.locator("#demo-token-input")).toBeVisible();
  await page.getByRole("button", { name: "Cancel" }).click();
  await expect(page.locator("#demo-token-input")).toHaveCount(0);
  await expect(page.getByRole("alert")).toHaveCount(0);
  await expect(page.getByTestId("inbox-R-2")).toHaveCount(0);
});

test("the phone approve page has the page menu, so Start over is one step", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await fresh(page);
  await stockOut(page);
  await page.goto("/approve/R-2");
  await expect(page.getByTestId("approve-question")).toBeVisible();
  await page.locator("#page-menu").click();
  await page.locator("#menu-reset").click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByTestId("inbox-R-2")).toHaveCount(0);
});
