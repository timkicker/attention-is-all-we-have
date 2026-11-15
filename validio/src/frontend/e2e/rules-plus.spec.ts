import { test, expect } from "@playwright/test";
import { fresh } from "./helpers";

// plans/025, R1 to R3 and F3: the orders on the scale, what the new limits would do, and the
// question before leaving with changes.
test("the Rules scale marks every order where it landed", async ({ page }) => {
  await fresh(page);
  await page.goto("/rules");
  await expect(page.getByTestId("dot-R-4")).toHaveAttribute("data-zone", "wait");
  await expect(page.getByTestId("dot-R-1")).toHaveAttribute("data-zone", "alone");
  await expect(page.getByTestId("rules-dots-cap")).toContainText("1 waited for you");
});

test("a higher alone limit repaints the waiting order and says so", async ({ page }) => {
  await fresh(page);
  await page.goto("/rules/edit");
  await page.locator("#f-alone").fill("1,600.00");
  await expect(page.getByTestId("dot-R-4")).toHaveAttribute("data-zone", "alone");
  await expect(page.getByTestId("what-if")).toContainText("4 ordered alone");
  await expect(page.getByTestId("save-bar")).toHaveClass(/live/);
});

test("leaving with changes asks; Stay keeps the form, Leave goes", async ({ page }) => {
  await fresh(page);
  await page.goto("/rules/edit");
  await page.locator("#f-alone").fill("1,300.00");
  await page.locator("#nav-home").click();
  await expect(page.getByTestId("leave-ask")).toBeVisible();
  await page.getByTestId("leave-stay").click();
  await expect(page.locator("h1")).toHaveText("Edit rules");
  await page.locator("#nav-home").click();
  await page.getByTestId("leave-go").click();
  await expect(page.locator("h1")).toHaveText("Home");
});
