import { test, expect } from "@playwright/test";

// Scene 3: stock-out, three substitutes blocked, one not deliverable, 463383
// found beyond the list, the owner approves on the phone.
test("scene 3: owner approves the swap", async ({ page }) => {
  await page.goto("/");
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await page.locator("#stock-out").click();
  await expect(page.locator("#inbox-R-2")).toContainText("Waiting for you");

  await page.locator("#inbox-R-2").click();
  await expect(page.locator("#simulated-stock-out")).toContainText("only in this demo");
  for (const id of ["466151", "468526", "475908"]) {
    await expect(page.locator(`#option-${id}`)).toContainText("Blocked");
  }
  await expect(page.locator("#option-473986")).toContainText("Not deliverable");
  await expect(page.locator("#option-463383")).toContainText("196.60");

  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator("#open-approve").click();
  await expect(page.locator("#question")).toContainText("Approve?");
  await page.locator("#approve").click();
  await expect(page.locator("#order-steps")).toContainText("Placed at Valio");
  await expect(page.locator("#approve")).toHaveCount(0);

  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/ledger");
  await expect(page.locator("#ledger")).toContainText("The owner approved 10 bags of 463383");
  await expect(page.locator("#chain-status")).toContainText("Chain verified");
});
