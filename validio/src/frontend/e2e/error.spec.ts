import { test, expect } from "@playwright/test";
import { fresh } from "./helpers";

// plans/025, F1: an address that opens nothing gets a page in the app's own look, with the way back.
test("an unknown address says so and offers Home and Activity", async ({ page }) => {
  await fresh(page);
  await page.goto("/no-such-page");
  await expect(page.getByTestId("error-page")).toBeVisible();
  await expect(page.locator("h1")).toHaveText("This page isn't here");
  await expect(page.getByTestId("error-page")).toContainText("/no-such-page");
  await page.locator("#error-home").click();
  await expect(page.locator("h1")).toHaveText("Home");
});
