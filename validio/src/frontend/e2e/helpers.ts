import { expect, type Page } from "@playwright/test";

/** A demo switch lives in the page menu behind the "⋯" in the top bar. */
export async function demo(page: Page, id: "stock-out" | "reset") {
  await page.locator("#page-menu").click();
  await page.locator(`#${id}`).click();
}

/** From a clean state: the fixture's state lives in localStorage. */
export async function fresh(page: Page) {
  await page.goto("/");
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await expect(page.locator("#inbox-R-1")).toBeVisible();
}

/** The fixture plays a server with the approval code set: any 6 digits. */
export const CODE = "246810";
