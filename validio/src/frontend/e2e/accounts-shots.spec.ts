import { test, expect, type Page } from "@playwright/test";
import { demoLogin, stockOut } from "./helpers";

// Screens of the account work, each state at 1280 and 390, light and dark.
// Runs only with ACCOUNT_SHOTS=<dir>: ACCOUNT_SHOTS=/tmp/shots npx playwright test accounts-shots
const OUT = process.env.ACCOUNT_SHOTS;
const VIEWS = [
  { width: 1280, height: 900, theme: "light" },
  { width: 1280, height: 900, theme: "dark" },
  { width: 390, height: 844, theme: "light" },
  { width: 390, height: 844, theme: "dark" },
] as const;

for (const v of VIEWS) {
  test(`account screens, ${v.width} ${v.theme}`, async ({ page }) => {
    test.skip(!OUT, "set ACCOUNT_SHOTS");
    await page.emulateMedia({ colorScheme: v.theme });
    await page.setViewportSize({ width: v.width, height: v.height });
    const shoot = async (name: string, p: Page = page) => {
      await p.waitForTimeout(250);
      await p.screenshot({ path: `${OUT}/${name}-${v.width}-${v.theme}.png`, fullPage: true });
    };
    const go = (path: string) => page.goto(`${path}${path.includes("?") ? "&" : "?"}theme=${v.theme}`);

    await go("/login");
    await page.evaluate(() => localStorage.clear());
    await go("/login");
    await expect(page.getByTestId("try-demo")).toBeVisible();
    await shoot("login");
    await page.getByTestId("login-submit").click();
    await shoot("login-problems");
    await page.getByTestId("login-swap").click();
    await shoot("signup");
    await page.getByTestId("login-submit").click();
    await shoot("signup-problems");
    await page.getByTestId("login-swap").click();
    await demoLogin(page);
    for (const [name, path] of [
      ["inbox", "/"],
      ["request", "/requests/R-1"],
      ["ledger", "/ledger"],
    ] as const) {
      await go(path);
      await page.waitForLoadState("networkidle");
      await shoot(name);
    }
    await stockOut(page);
    await go("/");
    await expect(page.getByTestId("inbox-R-2")).toBeVisible();
    await shoot("inbox-waiting");
    if (v.width === 1280) {
      await page.getByTestId("nav-orders").focus();
      await page.setViewportSize({ width: 900, height: 900 });
      await shoot("rail");
    }
  });
}
