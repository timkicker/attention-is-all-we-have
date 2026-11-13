import { test, expect } from "@playwright/test";
import { code, fresh } from "./helpers";

// Scene 4: the weekly order renews. Parmesan is split, pancakes wait, the
// mozzarella drift flag shows 26 %, and the history says it is simulated.
test("scene 4: steady order renews with flags", async ({ page }) => {
  await fresh(page);
  await page.goto("/steady");
  await page.getByTestId("steady-S-1").getByRole("link").click();
  await expect(page.getByTestId("simulated-history")).toContainText("Simulated history");

  // The first write asks for the approval code once, then runs.
  await page.getByTestId("renew").click();
  await code(page);
  await expect(page.getByTestId("line-464306")).toContainText("Renewed alone");
  await expect(page.getByTestId("line-463968")).toContainText("Split, renewed alone");
  await expect(page.getByTestId("line-463968")).toContainText("772.49");
  await expect(page.getByTestId("line-463968")).toContainText("2.5 %");
  await expect(page.getByTestId("line-471376")).toContainText("Waiting for you");
  await expect(page.getByTestId("line-471376")).toContainText("lists wheat as contained");
  await expect(page.getByTestId("line-466375")).toContainText("26 % more per guest");
  await expect(page.getByTestId("accept-466375")).toHaveText(/Renew anyway/);
  await expect(page.locator("#drift-466375")).toBeVisible();

  // The code is kept for the session: the second write does not ask again.
  await page.getByTestId("accept-471376").click();
  await expect(page.getByTestId("line-471376")).toContainText("Accepted");
  await expect(page.getByTestId("accept-471376")).toHaveCount(0);
  await expect(page.getByTestId("code-input")).toHaveCount(0);
  await page.getByTestId("nav-open-ledger").click();
  await expect(page.getByTestId("ledger")).toContainText("Chef accepted 27 cartons of 471376");
  await expect(page.getByTestId("chain-status")).toContainText("Chain verified");
});
