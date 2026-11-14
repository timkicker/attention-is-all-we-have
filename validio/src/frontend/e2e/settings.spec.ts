import { test, expect, type Page } from "@playwright/test";
import { fresh, slop } from "./helpers";

// Settings (builder B): Kitchen, Login, Approval code, Theme, Log out. Each
// change opens under its own row; the diet lives in the Rules now.

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
  await page.goto("/settings");
  await expect(page.getByTestId("section-kitchen")).toBeVisible();
}

test("the demo kitchen: four sections and Log out, no diet, no login to change", async ({ page }) => {
  await fresh(page);
  await page.locator("#nav-settings").click();
  await expect(page.locator("main h2")).toHaveText(["Kitchen", "Login", "Approval code", "Theme"]);
  await expect(page.getByText(/diet/i)).toHaveCount(0);
  await expect(page.getByTestId("kitchen-customer-change")).toHaveCount(0);
  await expect(page.getByTestId("login-demo-value")).toHaveText("None, this is a demo kitchen");
  await expect(page.getByTestId("code-value")).toHaveText("246810");
  await expect(page.getByTestId("code-change")).toHaveCount(0);
  await expect(page.getByTestId("log-out")).toBeVisible();
  expect(await slop(page)).toEqual([]);
});

test("the kitchen name changes in place and the sidebar follows; an empty name stays inline", async ({ page }) => {
  await fresh(page);
  await page.goto("/settings");
  await page.getByTestId("kitchen-name-change").click();
  await page.locator("#f-kitchen-name").fill("  ");
  await page.getByTestId("kitchen-name-save").click();
  await expect(page.getByTestId("f-kitchen-name-problem")).toHaveText("Type a name.");
  await expect(page.locator("#f-kitchen-name")).toBeFocused();
  await page.locator("#f-kitchen-name").fill("Hotel Espoo east kitchen");
  await page.getByTestId("kitchen-name-save").click();
  await expect(page.getByTestId("kitchen-name-value")).toHaveText("Hotel Espoo east kitchen");
  await expect(page.locator("#row-kitchen-name")).toContainText("Saved");
  await expect(page.locator("#nav-settings")).toContainText("Hotel Espoo east kitchen");

  await page.getByTestId("kitchen-address-change").click();
  await page.locator("#f-kitchen-address").fill("Kaivokatu 1, Espoo");
  await page.getByTestId("kitchen-address-save").click();
  await expect(page.getByTestId("kitchen-address-value")).toHaveText("Kaivokatu 1, Espoo");
  await expect(page.getByTestId("kitchen-name-value")).toHaveText("Hotel Espoo east kitchen");
});

test("email and password: problems under their field, a wrong password said so", async ({ page }) => {
  await ownKitchen(page);
  await expect(page.getByTestId("login-email-value")).toHaveText("chef@school.test");
  await page.getByTestId("login-email-change").click();
  await page.locator("#f-email").fill("chef@");
  await page.getByTestId("login-email-save").click();
  await expect(page.getByTestId("f-email-problem")).toHaveText("Type an email, like chef@kitchen.fi.");
  await expect(page.getByTestId("f-current-password-problem")).toHaveText("Type your current password.");
  await page.locator("#f-email").fill("head@school.test");
  await page.locator("#f-current-password").fill("short");
  await page.getByTestId("login-email-save").click();
  await expect(page.getByTestId("f-current-password-problem")).toHaveText("That password is not right.");
  await page.locator("#f-current-password").fill("long enough");
  await page.getByTestId("login-email-save").click();
  await expect(page.getByTestId("login-email-value")).toHaveText("head@school.test");

  await page.getByTestId("login-password-change").click();
  await page.locator("#f-password").fill("short");
  await page.locator("#f-current-password").fill("long enough");
  await page.getByTestId("login-password-save").click();
  await expect(page.getByTestId("f-password-problem")).toHaveText("At least 8 characters.");
  await page.locator("#login-password-cancel").click();
  await expect(page.getByTestId("login-password-form")).toHaveCount(0);
});

test("the approval code changes with the current one", async ({ page }) => {
  await ownKitchen(page);
  await page.getByTestId("code-change").click();
  await page.locator("#f-code-current").fill("12");
  await page.locator("#f-code-next").fill("abcdef");
  await page.getByTestId("code-save").click();
  await expect(page.getByTestId("f-code-current-problem")).toHaveText("Type your current 6-digit code.");
  await expect(page.getByTestId("f-code-next-problem")).toHaveText("Six digits, like 482913.");
  await page.locator("#f-code-current").fill("135790");
  await page.locator("#f-code-next").fill("482913");
  await page.getByTestId("code-save").click();
  await expect(page.getByTestId("code-form")).toHaveCount(0);
  await expect(page.locator("#row-code")).toContainText("Saved");
});

test("theme switches and stays, Log out goes to the login page", async ({ page }) => {
  await fresh(page);
  await page.goto("/settings");
  await page.locator("#theme").getByRole("radio", { name: "Light" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.locator("#theme").getByRole("radio", { name: "System" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.getByTestId("log-out").click();
  await expect(page).toHaveURL(/\/login$/);
});

test("phone: one column, no sideways scroll, Change opens under its row", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await ownKitchen(page);
  await expect(page.locator("h1")).toHaveText("Settings");
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await page.getByTestId("login-email-change").click();
  await expect(page.locator("#f-email")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});
