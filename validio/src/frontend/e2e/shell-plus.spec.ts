import { test, expect } from "@playwright/test";
import { fresh } from "./helpers";

// plans/025, S1 to S4 and F2, F4: the nav in the middle, the account menu, a badge that moves
// nothing, the line when the page is not live, and the palette's Review.
test("the nav sits in the middle of the band", async ({ page }) => {
  await fresh(page);
  const nav = await page.locator("nav.topnav").boundingBox();
  const vw = page.viewportSize()!.width;
  expect(Math.abs(nav!.x + nav!.width / 2 - vw / 2)).toBeLessThan(4);
});

test("the waiting badge does not move the nav words", async ({ page }) => {
  await fresh(page);
  await page.goto("/activity/R-4?approve=1");
  await expect(page.locator("#nav-home .nb")).toHaveCount(1);
  const before = await page.locator("#nav-activity").boundingBox();
  await page.keyboard.type("246810");
  await page.keyboard.press("Enter");
  await expect(page.locator("#nav-home .nb")).toHaveCount(0);
  const after = await page.locator("#nav-activity").boundingBox();
  expect(Math.abs(after!.x - before!.x)).toBeLessThan(0.5);
});

test("the account menu: keyboard opens it, theme switches, Escape closes", async ({ page }) => {
  await fresh(page);
  await page.locator("#nav-settings").focus();
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("account-menu")).toBeVisible();
  await page.getByTestId("menu-theme-dark").click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("account-menu")).toHaveCount(0);
  await expect(page.locator("#nav-settings")).toBeFocused();
});

test("offline shows one quiet line under the band", async ({ page, context }) => {
  await fresh(page);
  await context.setOffline(true);
  await page.evaluate(() => dispatchEvent(new Event("offline")));
  await expect(page.getByTestId("net-stale")).toContainText("You're offline.");
  await context.setOffline(false);
  await page.evaluate(() => dispatchEvent(new Event("online")));
  await expect(page.getByTestId("net-stale")).toHaveCount(0);
});

test("the palette puts what waits first and opens it with the code", async ({ page }) => {
  await fresh(page);
  await page.keyboard.press("ControlOrMeta+k");
  await expect(page.getByTestId("palette")).toBeVisible();
  await page.getByTestId("pal-review-R-4").click();
  await expect(page).toHaveURL(/\/activity\/R-4\?approve=1/);
  await expect(page.locator("#approve-code")).toBeVisible();
});
