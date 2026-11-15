import { test, expect } from "@playwright/test";
import { CODE, fresh } from "./helpers";

// plans/025, P1 to P4: the decision's spine, Approve as one landing with what comes next, the
// limits it was decided under, and Verify along the proof chain.
test("the spine is lit to the rule while the order waits", async ({ page }) => {
  await fresh(page);
  await page.goto("/activity/R-4");
  await expect(page.locator('.node[data-node="rule"]')).toHaveClass(/done/);
  await expect(page.locator('.node[data-node="result"]')).toHaveClass(/wait/);
  await expect(page.getByTestId("limits")).toContainText("Above what it orders alone");
});

test("a link with ?approve=1 opens the code; Approve lands and says what is next", async ({ page }) => {
  await fresh(page);
  await page.goto("/activity/R-4?approve=1");
  await expect(page.locator("#approve-code")).toBeFocused();
  await page.keyboard.type(CODE);
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("detail-status")).toHaveText("Approved by you");
  await expect(page.getByTestId("ending")).toContainText("Nothing else waits for you");
  await expect(page.locator('.node[data-node="result"]')).toHaveClass(/ok/);
  await expect(page.locator("#proof-toggle")).toContainText("3 entries");
  // The limits it was decided under stay beside it.
  await expect(page.getByTestId("limits")).toBeVisible();
});

test("Verify walks the proof chain and says it is sealed", async ({ page }) => {
  await fresh(page);
  await page.goto("/activity/R-1");
  await page.locator("#proof-toggle").click();
  await page.getByTestId("verify").click();
  await expect(page.getByTestId("verify-result")).toContainText("Sealed.");
  await expect(page.locator(".pe.vok")).toHaveCount(await page.locator(".pe").count());
});

test("Home approves in the row, and the row leaves", async ({ page }) => {
  await fresh(page);
  await page.getByTestId("approve-R-4").click();
  await page.keyboard.type(CODE);
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("need-R-4")).toHaveCount(0);
  await expect(page.getByTestId("toast").first()).toContainText("Approved");
  await expect(page.getByTestId("needs-none")).toBeVisible();
});
