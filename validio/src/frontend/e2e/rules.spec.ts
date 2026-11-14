import { test, expect, type Page } from "@playwright/test";
import { CODE, fresh, slop } from "./helpers";

// Rules (builder B): Money, Diet and allergens, Substitutes, each value once;
// Edit is one form with one Save that asks the approval code once.

const row = (page: Page, id: string) => page.locator(`#rule-${id}`);

async function ownKitchen(page: Page) {
  await page.goto("/login");
  await page.evaluate(() => localStorage.clear());
  await page.getByTestId("login-swap").click();
  await page.getByTestId("login-kitchen").fill("School kitchen");
  await page.getByTestId("login-email").fill("chef@school.test");
  await page.getByTestId("login-password").fill("long enough");
  await page.getByTestId("login-customer").fill("123456");
  await page.getByTestId("login-code").fill("135790");
  await page.getByTestId("login-submit").click();
  await expect(page.locator("h1")).toHaveText("Home");
}

async function edit(page: Page) {
  await page.locator("#rules-edit").click();
  await expect(page.locator("h1")).toHaveText("Edit rules");
  await expect(page.locator("#f-alone")).toBeVisible();
}

test("the three blocks say each rule once, with no summary on top", async ({ page }) => {
  await fresh(page);
  await page.locator("#nav-rules").click();
  await expect(page.getByTestId("rules-version")).toContainText("Version 2");
  await expect(row(page, "alone")).toContainText("Up to 1,200.00");
  await expect(row(page, "waiting")).toContainText("Up to 5,000.00");
  await expect(row(page, "blocked")).toContainText("Above 5,000.00");
  await expect(row(page, "week")).toContainText("Up to 8,000.00");
  await expect(row(page, "must")).toContainText("Lactose-free");
  await expect(row(page, "never")).toContainText("None");
  await expect(row(page, "allowed")).toContainText("From Valio's list");
  await expect(row(page, "extra")).toContainText("Up to 5 %");
  await expect(row(page, "unlisted")).toContainText("Waiting for you");
  // No sentence repeating them: the page holds 1,200.00 exactly once.
  expect((await page.locator("main").innerText()).match(/1,200\.00/g)).toHaveLength(1);
  expect(await slop(page)).toEqual([]);
});

test("one save asks the code once, a wrong code stays inline, the right one makes version 3", async ({ page }) => {
  await fresh(page);
  await page.goto("/rules");
  await edit(page);
  await expect(page.getByTestId("rules-changes")).toHaveText("No changes yet");
  await page.locator("#f-alone").fill("1500");
  await page.locator("#f-alone").blur();
  await expect(page.locator("#f-alone")).toHaveValue("1,500.00");
  await expect(page.locator("#row-alone")).toContainText("Was 1,200.00");
  await page.locator("#never-peanuts").click();
  await expect(page.locator("#never-peanuts")).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("rules-changes")).toHaveText("2 changes, in Money and Diet");

  await page.getByTestId("code-input").fill("111111");
  await page.getByTestId("code-submit").click();
  await expect(page.locator("#code-help")).toHaveText("That code is not right.");
  await expect(page).toHaveURL(/\/rules\/edit$/);

  await page.getByTestId("code-input").fill(CODE);
  await page.getByTestId("code-submit").click();
  await expect(page).toHaveURL(/\/rules\?saved$/);
  await expect(page.locator("#rules-saved")).toContainText("Saved");
  await expect(page.getByTestId("rules-version")).toContainText("Version 3");
  await expect(row(page, "alone")).toContainText("Up to 1,500.00");
  await expect(row(page, "never")).toContainText("Peanuts");
  // A request decided before the save keeps its version and says which one holds now.
  await page.goto("/activity/R-2");
  await expect(page.getByTestId("rule-version")).toHaveText("Rules, version 2 (now 3)");
});

test("problems show under their own field and nothing is saved", async ({ page }) => {
  await fresh(page);
  await page.goto("/rules/edit");
  await page.locator("#f-alone").fill("6000");
  await page.locator("#f-week").fill("abc");
  await page.locator("#f-extra").fill("40");
  await page.getByTestId("code-input").fill(CODE);
  await page.getByTestId("code-submit").click();
  await expect(page.getByTestId("f-alone-problem")).toHaveText("Must not be above Waiting for you.");
  await expect(page.getByTestId("f-week-problem")).toHaveText("Type an amount, like 1,200.00.");
  await expect(page.getByTestId("f-extra-problem")).toHaveText("A whole number from 0 to 20.");
  await expect(page.locator("#f-alone")).toBeFocused();
  await expect(page.locator("#f-alone")).toHaveAttribute("aria-invalid", "true");

  // A weekly limit under the approval limit, and the problem leaves once typed in again.
  await page.locator("#f-alone").fill("1200");
  await page.locator("#f-week").fill("4000");
  await page.locator("#f-extra").fill("10");
  await expect(page.getByTestId("f-alone-problem")).toHaveCount(0);
  await page.getByTestId("code-submit").click();
  await expect(page.getByTestId("f-week-problem")).toHaveText("At least 5,000.00 €, the Waiting for you limit.");
  await page.goto("/rules");
  await expect(page.getByTestId("rules-version")).toContainText("Version 2");
});

test("saving nothing says so, Never hides the extra cost, an empty week is no limit", async ({ page }) => {
  await fresh(page);
  await page.goto("/rules/edit");
  await page.getByTestId("code-input").fill(CODE);
  await page.getByTestId("code-submit").click();
  await expect(page.getByTestId("rules-changes")).toHaveText("Nothing changed yet.");

  await page.locator("#f-allowed").getByRole("radio", { name: "Never" }).click();
  await expect(page.locator("#f-extra")).toHaveCount(0);
  await page.locator("#f-week").fill("");
  await page.getByTestId("code-submit").click();
  await expect(page).toHaveURL(/\/rules\?saved$/);
  await expect(row(page, "allowed")).toContainText("Never");
  await expect(row(page, "any")).toContainText("Waiting for you");
  await expect(row(page, "extra")).toHaveCount(0);
  await expect(row(page, "week")).toContainText("No limit");
});

test("a kitchen made here sets its first rules", async ({ page }) => {
  await ownKitchen(page);
  await page.goto("/rules");
  await expect(page.getByText("No rules yet")).toBeVisible();
  await expect(page.locator("#rules-edit")).toHaveText("Set rules");
  await page.locator("#rules-edit").click();
  await page.locator("#f-alone").fill("800");
  await page.locator("#f-waiting").fill("3,000");
  await page.locator("#must-vegan").click();
  await page.getByTestId("code-input").fill("135790");
  await page.getByTestId("code-submit").click();
  await expect(page).toHaveURL(/\/rules\?saved$/);
  await expect(row(page, "alone")).toContainText("Up to 800.00");
  await expect(row(page, "waiting")).toContainText("Up to 3,000.00");
  await expect(row(page, "must")).toContainText("Vegan");
  await expect(row(page, "never")).toContainText("None");
});

test("phone: the fields sit under their labels and the page does not scroll sideways", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await fresh(page);
  await page.goto("/rules");
  await expect(row(page, "alone")).toBeVisible();
  await page.locator("#rules-edit").click();
  const label = await page.locator("#row-alone .label-title").boundingBox();
  const field = await page.locator("#f-alone").boundingBox();
  expect(field!.y).toBeGreaterThan(label!.y + label!.height - 1);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await page.locator("#f-alone").fill("1300");
  await page.getByTestId("code-input").fill(CODE);
  await page.getByTestId("code-submit").click();
  await expect(row(page, "alone")).toContainText("Up to 1,300.00");
});
