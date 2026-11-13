import { test, expect } from "@playwright/test";

// Scene 2: the milk is ranked and ordered alone; the ledger chain verifies.
test("scene 2: ordered alone, chain verified", async ({ page }) => {
  await page.goto("/");
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await expect(page.locator("#inbox-R-1")).toContainText("Ordered alone");

  await page.locator("#inbox-R-1").click();
  await expect(page.locator("#decision-sentence")).toContainText("Ordered 1000 ST of 464306");
  await expect(page.locator("#live-checked")).toContainText(/Checked \d+ products live/);
  await expect(page.locator("#option-464306")).toContainText("1,010.00");
  await expect(page.locator("#option-462921")).toContainText("hard cap");
  await expect(page.locator("#supplier-463047")).toContainText("Untrusted");
  await expect(page.locator("#spend-pass")).toContainText("1,200.00");

  await page.locator("#nav-open-ledger").click();
  await expect(page.locator("#chain-status")).toContainText("Chain verified");
  await expect(page.locator("#ledger")).not.toContainText("owner:anna");
});
