import { test, expect, type Page } from "@playwright/test";

// Not a scene test: walks every page in fixture mode and saves a screenshot at
// desktop and phone width, so a person can look at each one.
const OUT = "../../artifacts/shots";

async function shoot(page: Page, name: string) {
  for (const width of [1280, 390]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
    await page.waitForTimeout(150);
    await page.screenshot({ path: `${OUT}/${name}-${width}.png`, fullPage: true });
  }
  await page.setViewportSize({ width: 1280, height: 900 });
}

test("every page, both widths", async ({ page }) => {
  await page.goto("/");
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await expect(page.locator("#inbox-R-1")).toContainText("Ordered alone");
  await shoot(page, "inbox");

  await page.goto("/requests/R-1");
  await expect(page.locator("#decision-sentence")).toContainText("Ordered 1000 ST of 464306");
  await shoot(page, "request-milk");

  await page.goto("/");
  await page.locator("#stock-out").click();
  await expect(page.locator("#inbox-R-2")).toContainText("Waiting for you");
  await shoot(page, "inbox-waiting");

  await page.goto("/requests/R-2");
  await expect(page.locator("#decision-sentence")).toContainText("Grated Maestrella");
  await shoot(page, "request-mozzarella");

  await page.goto("/approve/R-2");
  await expect(page.locator("#question")).toContainText("Approve?");
  await shoot(page, "approve");
  await page.locator("#approve").click();
  await expect(page.locator("#order-steps")).toContainText("Placed at Valio");
  await shoot(page, "approve-done");

  await page.goto("/ledger");
  await expect(page.locator("#chain-status")).toContainText("Chain verified");
  await page.locator("#entry-2-details").click();
  await shoot(page, "ledger");
});
