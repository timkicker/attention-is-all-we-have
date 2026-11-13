import { test, expect } from "@playwright/test";

// Scene 4: the weekly order renews. Parmesan is split, pancakes wait, the
// mozzarella drift flag shows 26 %, and the history says it is simulated.
test("scene 4: steady order renews with flags", async ({ page }) => {
  await page.goto("/");
  await page.evaluate(() => localStorage.clear());
  await page.goto("/steady");
  await page.getByRole("link", { name: /Weekly Monday order/ }).click();
  await expect(page.locator("#simulated-history")).toContainText("Simulated history");

  await page.locator("#renew").click();
  await expect(page.locator("#line-464306")).toContainText("Renewed alone");
  await expect(page.locator("#line-463968")).toContainText("Split, renewed alone");
  await expect(page.locator("#line-463968")).toContainText("772.49");
  await expect(page.locator("#line-463968")).toContainText("2.5 %");
  await expect(page.locator("#line-471376")).toContainText("Waiting for you");
  await expect(page.locator("#line-471376")).toContainText("476523 contains wheat");
  await expect(page.locator("#line-466375")).toContainText("26 % more mozzarella per guest");

  await page.locator("#accept-471376").click();
  await expect(page.locator("#line-471376")).toContainText("Accepted");
  await page.goto("/ledger");
  await expect(page.locator("#ledger")).toContainText("The chef ordered 27 cartons");
  await expect(page.locator("#chain-status")).toContainText("Chain verified");
});
