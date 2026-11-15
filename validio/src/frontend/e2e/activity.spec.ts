import { test, expect } from "@playwright/test";
import { fresh, slop } from "./helpers";

// Activity in fixture mode: filter chips with counts in the address, day heads.

test("chips carry counts and filter through ?status=", async ({ page }) => {
  await fresh(page);
  await page.goto("/activity");
  await expect(page.locator("#filter-all")).toHaveAttribute("aria-pressed", "true");
  for (const [f, n] of [["all", "8"], ["ordered", "5"], ["waiting", "1"], ["blocked", "1"], ["standing", "1"]]) {
    await expect(page.locator(`#filter-${f}`)).toContainText(n);
  }
  await expect(page.locator("a.ar")).toHaveCount(8);
  await page.locator("#filter-ordered").click();
  await expect(page).toHaveURL(/\?status=ordered$/);
  await expect(page.locator("#filter-ordered")).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("a.ar")).toHaveCount(5);
  await expect(page.locator('a.ar[data-status="ordered"]')).toHaveCount(5);
  await page.locator("#filter-all").click();
  await expect(page).toHaveURL(/\/activity$/);
  await expect(page.locator("a.ar")).toHaveCount(8);
});

test("a filter in the address opens with it, Back walks the filters", async ({ page }) => {
  await fresh(page);
  await page.goto("/activity?status=waiting");
  await expect(page.locator("#filter-waiting")).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("a.ar")).toHaveCount(1);
  await page.locator("#filter-blocked").click();
  await expect(page.getByTestId("activity-R-3")).toBeVisible();
  await page.goBack();
  await expect(page.getByTestId("activity-R-4")).toBeVisible();
  await expect(page.locator("a.ar")).toHaveCount(1);
});

test("rows sit under their day, newest first", async ({ page }) => {
  await fresh(page);
  await page.goto("/activity");
  await expect(page.locator("h2.v-h")).toHaveText(["Today, Sat 14 Nov", "Fri 13 Nov", "Sat 7 Nov"]);
  expect(await slop(page)).toEqual([]);
  await page.getByTestId("activity-R-1").click();
  await expect(page).toHaveURL(/\/activity\/R-1$/);
});

test("an empty kitchen: no chips, one line", async ({ page }) => {
  await page.goto("/login");
  await page.evaluate(() => localStorage.clear());
  await page.getByTestId("login-swap").click();
  await page.getByTestId("login-kitchen").fill("School kitchen");
  await page.getByTestId("login-email").fill("chef@school.test");
  await page.getByTestId("login-password").fill("long enough");
  await page.getByTestId("login-customer").fill("123456");
  await page.getByTestId("login-code").fill("135790");
  await page.getByTestId("login-submit").click();
  await page.goto("/activity");
  await expect(page.getByText("Nothing yet")).toBeVisible();
  await expect(page.locator("#filter-all")).toHaveCount(0);
});

test("phone: the chips scroll on their own, the page does not", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await fresh(page);
  await page.goto("/activity");
  await expect(page.getByTestId("activity-R-4")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});
