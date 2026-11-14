import { test, expect } from "@playwright/test";

// The login page: what Validio is in one sentence, Log in, Create account with
// its five fields, and the demo kitchen with its approval code.
test.beforeEach(async ({ page }) => {
  await page.goto("/login");
  await page.evaluate(() => localStorage.clear());
  await page.reload();
});

test("one sentence, log in, and the demo kitchen with its code", async ({ page }) => {
  await expect(page.locator("h1")).toHaveText("Validio");
  await expect(page.getByTestId("login-what")).toContainText("Valio Aimo");
  await expect(page.locator("#door-h")).toHaveText("Log in");
  await expect(page.getByTestId("try-demo")).toHaveText("Try the demo kitchen");
  await expect(page.locator("#demo-what")).toHaveText("A real kitchen with sample orders. Approval code: 246810");
  await expect(page.locator("body")).not.toContainText(/claude/i);
});

test("create account asks name, email, password, customer number and code", async ({ page }) => {
  await page.getByTestId("login-swap").click();
  await expect(page.locator("#door-h")).toHaveText("Create account");
  for (const id of ["login-kitchen", "login-email", "login-password", "login-customer", "login-code"]) await expect(page.getByTestId(id)).toBeVisible();
  await expect(page.locator("#login-kitchen")).toBeFocused();
  await page.getByTestId("login-code").fill("12");
  await page.getByTestId("login-submit").click();
  await expect(page.getByTestId("login-code-problem")).toHaveText("6 digits.");
  await page.getByTestId("login-swap").click();
  await expect(page.locator("#door-h")).toHaveText("Log in");
  await expect(page.getByTestId("login-kitchen")).toHaveCount(0);
});

test("the login page fits a 390 px phone in both modes", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const over = () => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(await over()).toBeLessThanOrEqual(0);
  await page.getByTestId("login-swap").click();
  expect(await over()).toBeLessThanOrEqual(0);
});
