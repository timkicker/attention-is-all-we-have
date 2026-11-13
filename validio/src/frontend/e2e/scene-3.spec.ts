import { test, expect } from "@playwright/test";
import { CODE, demo, fresh } from "./helpers";

// Scene 3: stock-out, three listed substitutes blocked, one not deliverable,
// the mozzarella-fontal blend 465256 found beyond the list, the owner approves
// on the phone with the code.
test("scene 3: owner approves the swap", async ({ page }) => {
  await fresh(page);
  await demo(page, "stock-out");
  await expect(page.locator("#inbox-R-2")).toContainText("Waiting for you");

  await page.locator("#inbox-R-2").click();
  await expect(page.locator("#simulated-stock-out")).toContainText("only in this demo");
  for (const id of ["466151", "468526", "475908"]) {
    await expect(page.locator(`#option-${id}`)).toContainText("Blocked");
  }
  await expect(page.locator("#option-473986")).toContainText("Not deliverable");
  await expect(page.locator("#option-465256")).toContainText("180.10");
  await expect(page.locator("#option-465256")).toContainText("Chosen");
  await expect(page.locator("#option-463383")).toContainText("196.60");

  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator("#open-approve").click();
  await expect(page.locator("#question")).toHaveText("Approve 10 packs of 465256 for 180.10 €?");

  // Without the code nothing happens; with it the order is placed.
  await page.locator("#approve").click();
  await expect(page.locator("#code-help")).toContainText("6 digit");
  await page.locator("#approve-code").fill(CODE);
  await page.locator("#approve").click();
  await expect(page.locator("#order-steps")).toContainText("Placed at Valio");
  await expect(page.locator("#approve")).toHaveCount(0);

  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/ledger");
  await expect(page.locator("#ledger")).toContainText("Owner approved 10 ST of 465256 for 180.10 EUR");
  await expect(page.locator("#chain-status")).toContainText("Chain verified");
});
