import { test, expect } from "@playwright/test";
import { fresh, reset } from "./helpers";

// The v2 shell in fixture mode: four places and Settings, the old addresses
// land on their v2 pages, the demo bar, the phone's top line and tab bar.
// Page builders add their own specs next to this one.

test("sidebar holds Home, Activity, Rules, Agent and the kitchen opens Settings", async ({ page }) => {
  await fresh(page);
  for (const [id, h1] of [["nav-activity", "Activity"], ["nav-rules", "Rules"], ["nav-agent", "Agent"], ["nav-home", "Home"]]) {
    await page.locator(`#${id}`).click();
    await expect(page.locator("h1")).toHaveText(h1);
    await expect(page.locator(`#${id}`)).toHaveAttribute("aria-current", "page");
  }
  await expect(page.locator("#nav-home")).toContainText("1");
  await page.locator("#nav-settings").click();
  await expect(page.locator("h1")).toHaveText("Settings");
  await expect(page.locator("#page-menu")).toHaveCount(0);
});

test("old addresses land on their v2 pages", async ({ page }) => {
  await fresh(page);
  for (const [from, to] of [
    ["/orders", /\/activity$/],
    ["/ledger", /\/activity$/],
    ["/requests/R-1", /\/activity\/R-1$/],
    ["/approve/O-7", /\/activity\?status=waiting$/],
    ["/spend-pass", /\/rules$/],
    ["/steady", /\/activity\?status=standing$/],
    ["/steady/S-1", /\/activity\/S-1$/],
  ] as const) {
    await page.goto(from);
    await expect(page).toHaveURL(to);
  }
});

test("demo bar resets and the activity rows come from the fixture", async ({ page }) => {
  await fresh(page);
  await expect(page.getByTestId("demo-bar")).toContainText("Demo kitchen");
  await page.goto("/activity");
  await expect(page.getByTestId("activity-R-4")).toContainText("Waiting for you");
  await expect(page.getByTestId("activity-R-4")).toContainText("1,515.00");
  await expect(page.getByTestId("activity-R-3")).toContainText("Blocked");
  await expect(page.getByTestId("activity-R-1")).toContainText("Ordered alone");
  await expect(page.getByTestId("activity-S-1")).toContainText("Standing");
  await reset(page);
  await expect(page.locator("h1")).toHaveText("Home");
});

test("a kitchen made here has no demo bar and no activity", async ({ page }) => {
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
  await expect(page.getByTestId("demo-bar")).toHaveCount(0);
  await page.goto("/activity");
  await expect(page.getByText("Nothing yet")).toBeVisible();
});

test("phone: kitchen name on top, tab bar at the bottom", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await fresh(page);
  await expect(page.locator("#phone-settings")).toContainText("Hotel Espoo kitchen");
  await page.locator("#nav-activity-tab").click();
  await expect(page.locator("h1")).toHaveText("Activity");
  await page.locator("#phone-settings").click();
  await expect(page.locator("h1")).toHaveText("Settings");
});
