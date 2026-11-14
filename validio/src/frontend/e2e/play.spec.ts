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
  const final = page.getByTestId("ask-final");
  await expect(final).toContainText("no backend");
  await expect(final).not.toHaveClass(/bad/);
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
