import { test, expect, type Page } from "@playwright/test";
import { CODE, demoLogin, slop } from "./helpers";

// Settings, the Inbox checklist and the example request in every state, at
// 1280 and 390, light and dark. Runs only with SETTINGS_SHOTS=<dir>.
const OUT = process.env.SETTINGS_SHOTS;
const VIEWS = [
  { width: 1280, height: 900, theme: "light" },
  { width: 1280, height: 900, theme: "dark" },
  { width: 390, height: 844, theme: "light" },
  { width: 390, height: 844, theme: "dark" },
] as const;

for (const v of VIEWS) {
  test(`settings screens, ${v.width} ${v.theme}`, async ({ page }) => {
    test.skip(!OUT, "set SETTINGS_SHOTS");
    await page.emulateMedia({ colorScheme: v.theme });
    await page.setViewportSize({ width: v.width, height: v.height });
    const problems: string[] = [];
    const shoot = async (name: string, p: Page = page) => {
      await p.waitForTimeout(250);
      await p.screenshot({ path: `${OUT}/${name}-${v.width}-${v.theme}.png`, fullPage: true });
      problems.push(...(await slop(p)).map((x) => `${name}: ${x}`));
    };
    const go = (path: string) => page.goto(`${path}${path.includes("?") ? "&" : "?"}theme=${v.theme}`);
    const phone = v.width < 761;

    // A new account: the checklist with nothing done.
    await go("/login");
    await page.evaluate(() => localStorage.clear());
    await go("/login");
    await page.getByTestId("login-swap").click();
    await page.locator("#login-kitchen").fill("Ravintola Kumpula");
    await page.locator("#login-email").fill("chef@example.org");
    await page.locator("#login-password").fill("long enough");
    await page.locator("#login-customer").fill("12345");
    await page.locator("#login-code").fill(CODE);
    await page.getByTestId("login-submit").click();
    await expect(page.getByTestId("setup")).toBeVisible();
    await shoot("checklist-new");

    // Settings of a real account.
    await go(phone ? "/settings" : "/settings/kitchen");
    if (phone) {
      await expect(page.getByTestId("set-row-kitchen")).toBeVisible();
      await shoot("settings-list");
      await page.getByTestId("set-row-kitchen").click();
    }
    await expect(page.getByTestId("kitchen-name")).toContainText("Ravintola Kumpula");
    await shoot("settings-kitchen");
    await page.getByTestId("kitchen-edit").click();
    await page.locator("#f-kitchen-name").fill("");
    await page.getByTestId("kitchen-save").click();
    await expect(page.getByTestId("f-kitchen-name-problem")).toBeVisible();
    await shoot("settings-kitchen-problem");
    await page.locator("#f-kitchen-name").fill("Ravintola Kumpula");
    await page.locator("#f-kitchen-address").fill("Gustaf Hällströmin katu 2, 00560 Helsinki");
    await shoot("settings-kitchen-edit");
    await page.getByTestId("kitchen-save").click();
    await expect(page.getByTestId("kitchen-address")).toContainText("Helsinki");
    await shoot("settings-kitchen-saved");

    await go("/");
    await expect(page.getByTestId("setup")).toContainText("1 of 3");
    await shoot("checklist-kitchen-done");

    await go("/settings/login");
    await expect(page.getByTestId("login-email")).toContainText("chef@example.org");
    await shoot("settings-login");
    await page.getByTestId("login-change-email").click();
    await page.getByTestId("login-save").click();
    await shoot("settings-login-problems");
    await page.locator("#f-email").fill("kitchen@example.org");
    await page.locator("#f-current-password").fill("long enough");
    await page.getByTestId("login-save").click();
    await expect(page.getByTestId("login-email")).toContainText("kitchen@example.org");
    await page.getByTestId("login-change-code").click();
    await shoot("settings-login-code");

    // The demo kitchen.
    await go("/login");
    await page.evaluate(() => localStorage.clear());
    await go("/login");
    await demoLogin(page);
    await go("/");
    await expect(page.getByTestId("example")).toBeVisible();
    await shoot("inbox-example");
    await page.getByTestId("example-send").click();
    // The fixture's answer is the recorded milk request, already in the list: no second row.
    await expect(page.getByTestId("example-send")).toBeEnabled();
    await shoot("inbox-example-sent");

    await go("/settings/diet");
    await expect(page.getByTestId("diet-FREE_FROM_LACTOSE")).toHaveAttribute("aria-checked", "true");
    await shoot("settings-diet");
    await page.getByTestId("diet-FREE_FROM_GLUTEN").click();
    await shoot("settings-diet-changed");
    await page.getByTestId("diet-save").click();
    await expect(page.getByTestId("code-input")).toBeFocused();
    await shoot("settings-diet-code");
    await page.getByTestId("code-input").fill("12");
    await page.getByTestId("code-submit").click();
    await shoot("settings-diet-code-problem");
    await page.getByTestId("code-input").fill(CODE);
    await page.getByTestId("code-submit").click();
    await expect(page.getByTestId("diet-saved")).toBeVisible();
    await shoot("settings-diet-saved");

    await go("/settings/login");
    await shoot("settings-login-demo");
    await go("/settings/theme");
    await expect(page.getByTestId("theme")).toBeVisible();
    await shoot("settings-theme");

    if (phone) await go("/settings");
    await page.getByTestId("log-out").click();
    await expect(page).toHaveURL(/\/login/);

    expect(problems).toEqual([]);
  });
}
