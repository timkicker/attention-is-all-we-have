import { test, expect, type Page } from "@playwright/test";
import { code, fresh, slop, stockOut } from "./helpers";

// Orders: requests and steady orders in one list, filtered by chips. The old
// list addresses land on it.
test("orders lists requests and steady orders, chips filter", async ({ page }) => {
  await fresh(page);
  await page.goto("/orders");
  await expect(page.getByTestId("order-r-R-1")).toContainText("Ordered alone");
  await expect(page.getByTestId("order-s-S-1")).toContainText("Not renewed yet");
  await expect(page.getByTestId("order-s-S-1")).toHaveAttribute("href", "/steady/S-1");

  await page.locator("#filter-steady").click();
  await expect(page).toHaveURL(/\/orders\?f=steady$/);
  await expect(page.getByTestId("order-s-S-1")).toBeVisible();
  await expect(page.getByTestId("order-r-R-1")).toHaveCount(0);

  await page.locator("#filter-ordered").click();
  await expect(page.getByTestId("order-r-R-1")).toBeVisible();
  await expect(page.getByTestId("order-s-S-1")).toHaveCount(0);
  await expect(page.locator("#filter-ordered")).toHaveAttribute("aria-pressed", "true");

  await page.locator("#filter-all").click();
  await expect(page).toHaveURL(/\/orders$/);
  await page.getByTestId("order-r-R-1").click();
  await expect(page).toHaveURL(/\/requests\/R-1$/);
});

test("the old lists redirect to orders", async ({ page }) => {
  await fresh(page);
  await page.goto("/steady");
  await expect(page).toHaveURL(/\/orders\?f=steady$/);
  await expect(page.locator("#filter-steady")).toHaveAttribute("aria-pressed", "true");
  await page.goto("/requests");
  await expect(page).toHaveURL(/\/orders$/);
  await expect(page.getByTestId("order-r-R-1")).toBeVisible();
});

test("a renewed steady order with an open line counts as waiting", async ({ page }) => {
  await fresh(page);
  await stockOut(page);
  await page.goto("/steady/S-1");
  await page.getByTestId("renew").click();
  await code(page);
  await expect(page.getByTestId("accept-471376")).toBeVisible();
  await page.goto("/orders?f=waiting");
  await expect(page.getByTestId("order-s-S-1")).toContainText("Waiting for you");
});

// Shots of every state at 1280 and 390, light and dark. Only with ORDERS_SHOTS=<dir>.
const OUT = process.env.ORDERS_SHOTS;
const VIEWS = [
  { width: 1280, height: 900, theme: "light" },
  { width: 1280, height: 900, theme: "dark" },
  { width: 390, height: 844, theme: "light" },
  { width: 390, height: 844, theme: "dark" },
] as const;

for (const v of VIEWS) {
  test(`orders shots, ${v.width} ${v.theme}`, async ({ page }) => {
    test.skip(!OUT, "set ORDERS_SHOTS");
    await page.emulateMedia({ colorScheme: v.theme });
    await page.setViewportSize({ width: v.width, height: v.height });
    const problems: string[] = [];
    const go = (path: string) => page.goto(`${path}${path.includes("?") ? "&" : "?"}theme=${v.theme}`);
    const shoot = async (name: string, p: Page = page) => {
      await p.waitForTimeout(250);
      await p.screenshot({ path: `${OUT}/${name}-${v.width}-${v.theme}.png`, fullPage: true });
      problems.push(...(await slop(p)).map((x) => `${name}: ${x}`));
    };

    await fresh(page);
    for (const f of ["all", "waiting", "ordered", "blocked", "steady"]) {
      await go(f === "all" ? "/orders" : `/orders?f=${f}`);
      await expect(page.locator(`#filter-${f}`)).toHaveAttribute("aria-pressed", "true");
      await shoot(`orders-${f}`);
    }
    await stockOut(page);
    await go("/steady/S-1");
    await page.getByTestId("renew").click();
    await code(page);
    await expect(page.getByTestId("accept-471376")).toBeVisible();
    await shoot("steady-renewed");
    await go("/orders");
    await expect(page.getByTestId("order-s-S-1")).toContainText("Waiting for you");
    await shoot("orders-after-renew");
    expect(problems).toEqual([]);
  });
}
