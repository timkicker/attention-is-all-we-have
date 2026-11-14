import { test, expect } from "@playwright/test";
import { demoLogin } from "./helpers";

// F1: nobody logged in lands on /login; the demo button, sign up and log in each open the app.
test.beforeEach(async ({ page }) => {
  await page.goto("/login");
  await page.evaluate(() => localStorage.clear());
});

test("a page without a session goes to the login page", async ({ page }) => {
  await page.goto("/activity");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByTestId("try-demo")).toBeVisible();
});

test("the demo kitchen opens Home and stays after a reload", async ({ page }) => {
  await demoLogin(page);
  await expect(page.locator("h1")).toHaveText("Home");
  await expect(page.getByTestId("demo-bar")).toContainText("Demo kitchen");
  await page.reload();
  await expect(page.locator("h1")).toHaveText("Home");
  await page.goto("/login");
  await expect(page).not.toHaveURL(/\/login/);
});

test("sign up checks each field, then opens the app under the new name", async ({ page }) => {
  await page.getByTestId("login-swap").click();
  await page.getByTestId("login-submit").click();
  await expect(page.getByTestId("login-kitchen-problem")).toBeVisible();
  await expect(page.getByTestId("login-code-problem")).toBeVisible();
  await page.getByTestId("login-kitchen").fill("School kitchen");
  await page.getByTestId("login-email").fill("chef@school.test");
  await page.getByTestId("login-password").fill("long enough");
  await page.getByTestId("login-customer").fill("123456");
  await page.getByTestId("login-code").fill("135790");
  await page.getByTestId("login-submit").click();
  await expect(page).not.toHaveURL(/\/login/);
  await expect(page.getByText("School kitchen").first()).toBeVisible();

  // Log out by dropping the session, then log in with the same account.
  await page.evaluate(() => localStorage.removeItem("validio-mock-session"));
  await page.goto("/login");
  await page.getByTestId("login-email").fill("chef@school.test");
  await page.getByTestId("login-password").fill("wrong one");
  await page.getByTestId("login-submit").click();
  await expect(page.getByTestId("login-password-problem")).toHaveText("Email or password is wrong.");
  await page.getByTestId("login-password").fill("long enough");
  await page.getByTestId("login-submit").click();
  await expect(page).not.toHaveURL(/\/login/);
});
