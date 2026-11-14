import { test, expect } from "@playwright/test";
import { code, fresh, stockOut } from "./helpers";

// Scene 3: stock-out, three listed substitutes blocked, one not deliverable,
// the mozzarella-fontal blend 465256 found beyond the list, the owner approves
// on the phone with the code.
test("scene 3: owner approves the swap", async ({ page }) => {
  await fresh(page);
  await stockOut(page);
  await page.goto("/");
  await expect(page.getByTestId("inbox-summary-R-2")).toContainText("The swap needs you");
  await expect(page.getByTestId("inbox-R-2")).toContainText("Waiting for you");

  await page.getByTestId("inbox-R-2").click();
  await expect(page.locator("#request-title")).toContainText("200 bags of");
  await expect(page.locator("#request-why")).toHaveText("Out of stock (simulated). Swap not on Valio's list.");
  // The live count sits in the chosen row's fold.
  await expect(page.getByTestId("asked-for")).toContainText("11,603");
  // Beyond the list is open first: the chosen blend.
  await expect(page.getByTestId("option-465256")).toContainText("180.10");
  await expect(page.getByTestId("option-465256")).toContainText("Chosen");
  await page.locator("#tab-list").click();
  for (const id of ["466151", "468526", "475908"]) {
    await expect(page.getByTestId(`option-${id}`)).toContainText("Blocked");
  }
  await expect(page.getByTestId("option-473986")).toContainText("Not deliverable");

  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByTestId("open-approve").click();
  await expect(page.getByTestId("approve-question")).toHaveText(/^Order 10\s×\s2\.5\skg of mozzarella-fontal crumbled cheese for 180\.10\s€\?$/);

  // The code is asked when the owner presses Approve; with it the order is placed.
  await expect(page.getByTestId("code-input")).toHaveCount(0);
  await page.getByTestId("approve").click();
  await expect(page.locator("#code-help")).toContainText("246810"); // the code prompt names the demo code
  await code(page);
  await expect(page.getByTestId("order-done")).toContainText("confirmed again");
  await expect(page.getByTestId("approve")).toHaveCount(0);

  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/ledger");
  await expect(page.getByTestId("ledger")).toContainText("Owner approved 10 × 2.5 kg of mozzarella-fontal crumbled cheese for 180.10 €");
  await expect(page.getByTestId("chain-status")).toContainText("Verified");
});
