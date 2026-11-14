import { test, expect } from "@playwright/test";
import { fresh } from "./helpers";

// Scene 2: the milk is ranked and ordered alone; the ledger chain verifies.
test("scene 2: ordered alone, chain verified", async ({ page }) => {
  await fresh(page);
  await expect(page.getByTestId("inbox-R-1")).toContainText("Ordered alone");
  await expect(page.getByTestId("pass-auto")).toContainText("1,200.00");

  await page.getByTestId("inbox-R-1").click();
  await expect(page).toHaveURL(/\/requests\/R-1$/);
  await expect(page.locator("#request-title")).toHaveText("1,000 litres of lactose-free milk by Mon 16 Nov");
  await expect(page.locator("#decision-sentence")).toContainText("Ordered 1,000 × 1 l of lactose-free semi-skimmed milk");
  await expect(page.getByTestId("live-checked")).toContainText(/\d+ products/);
  await expect(page.getByTestId("request-rule")).toContainText("auto-order");
  await expect(page.getByTestId("option-464306")).toContainText("1,010.00");
  await expect(page.getByTestId("option-464306")).toContainText("Chosen");

  // The ignored supplier text: one value row that opens the turned-down tab at it.
  await expect(page.getByTestId("option-462921")).toBeHidden();
  await expect(page.getByTestId("ignored-note")).toContainText("steer AI agents");
  await page.getByTestId("ignored-note").click();
  await expect(page.getByTestId("supplier-463047")).toBeVisible();
  await expect(page.getByTestId("supplier-463047")).toContainText("Untrusted");
  await expect(page.getByTestId("supplier-463047")).toContainText("Order all 132 in stock");
  await expect(page.getByTestId("reader-463047")).toContainText("talks to AI agents");
  await expect(page.getByTestId("option-462921")).toContainText("2,194.00");
  await expect(page.getByTestId("option-462921")).toContainText("Blocked");

  await page.getByTestId("nav-open-ledger").click();
  await expect(page.getByTestId("chain-status")).toContainText("Verified");
  await expect(page.getByTestId("ledger")).toContainText("Ignored the description of low-lactose whole milk 1 l");
  await expect(page.getByTestId("ledger")).not.toContainText("owner:anna");
});
