import { test, expect } from "@playwright/test";
import { code, fresh, stockOut } from "./helpers";

// Scene 4: the weekly order renews. Parmesan is split, pancakes wait, the
// mozzarella line is not ordered and shows its drift, and the history says it is simulated.
test("scene 4: steady order renews with flags", async ({ page }) => {
  await fresh(page);
  // As in the demo: the stock-out of scene 3 comes first, so the mozzarella line is blocked.
  await stockOut(page);
  await page.goto("/steady");
  await page.getByTestId("steady-S-1").click();
  await expect(page.getByTestId("simulated-history")).toContainText("simulated");

  // The first write asks for the approval code once, then runs.
  await page.getByTestId("renew").click();
  await code(page);
  await expect(page.getByTestId("line-464306")).toContainText("Renewed");
  await expect(page.getByTestId("line-463968")).toContainText("Renewed");
  await expect(page.getByTestId("line-463968")).toContainText("772.49");
  await expect(page.getByTestId("line-463968")).toContainText("2.5 %");
  await expect(page.getByTestId("accept-471376")).toHaveText(/Order 27 now/);
  await expect(page.getByTestId("line-471376")).toContainText(/wheat as contained/i);
  await expect(page.getByTestId("line-466375")).toContainText("26 % more per guest");
  await expect(page.getByTestId("line-466375").getByRole("img")).toBeVisible();
  await expect(page.getByTestId("accept-466375")).toHaveCount(0);

  // The code is kept for the session: the second write does not ask again.
  await page.getByTestId("accept-471376").click();
  await expect(page.getByTestId("line-471376")).toContainText("Accepted");
  await expect(page.getByTestId("accept-471376")).toHaveCount(0);
  await expect(page.getByTestId("code-input")).toHaveCount(0);
  await page.getByTestId("nav-open-ledger").click();
  await expect(page.getByTestId("ledger")).toContainText("Owner accepted 27 cartons of vegan pancake 30 g");
  await expect(page.getByTestId("chain-status")).toContainText("Verified");
});
