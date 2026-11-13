import { test, expect, type Page } from "@playwright/test";
import { CODE, demo, fresh } from "./helpers";

// Not a scene test: walks every page in fixture mode and saves a screenshot at
// desktop and phone width, in the dark and the light theme, so a person can
// look at each one. Files: ../../artifacts/shots/<page>-<width>-<theme>.png
const OUT = "../../artifacts/shots";

for (const theme of ["dark", "light"] as const) {
  test(`every page, both widths, ${theme}`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: theme });
    const go = (path: string) => page.goto(`${path}${path.includes("?") ? "&" : "?"}theme=${theme}`);
    async function shoot(name: string) {
      for (const width of [1280, 390]) {
        await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
        await page.waitForTimeout(200);
        await page.screenshot({ path: `${OUT}/${name}-${width}-${theme}.png`, fullPage: width === 390 });
      }
      await page.setViewportSize({ width: 1280, height: 900 });
    }

    await fresh(page);
    await go("/");
    await expect(page.locator("#inbox-R-1")).toContainText("Ordered alone");
    await shoot("inbox");

    await go("/requests/R-1");
    await expect(page.locator("#decision-sentence")).toContainText("Ordered 1000 ST of 464306");
    await shoot("request-milk");
    await page.locator("#fold-options").click();
    await page.locator("#option-464306 button.open").click();
    await page.locator("#option-463047").scrollIntoViewIfNeeded();
    await shoot("request-milk-open");

    await demo(page, "stock-out");
    await expect(page.locator("#decision-sentence")).toContainText("465256");
    await shoot("request-mozzarella");

    await go("/approve/O-2");
    await expect(page.locator("#question")).toContainText("Approve");
    await shoot("approve");
    await page.locator("#approve-code").fill(CODE);
    await page.locator("#approve").click();
    await expect(page.locator("#order-steps")).toContainText("Placed at Valio");
    await shoot("approve-done");

    await go("/steady");
    await shoot("steady-list");
    await go("/steady/S-1");
    await expect(page.locator("#simulated-history")).toBeVisible();
    await shoot("steady-before");
    await page.locator("#renew").click();
    await page.locator("#approve-code").fill(CODE);
    await page.locator("#use-code").click();
    await expect(page.locator("#line-466375")).toContainText("26 %");
    await shoot("steady-renewed");

    await go("/spend-pass");
    await expect(page.locator("#pass-auto")).toContainText("1,200.00");
    await shoot("spend-pass");

    await go("/ledger");
    await expect(page.locator("#chain-status")).toContainText("Chain verified");
    await page.locator("#entry-8 button.line").click();
    await shoot("ledger");
  });
}
