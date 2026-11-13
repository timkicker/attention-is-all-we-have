import { test, expect, type Page } from "@playwright/test";
import { code, fresh, slop, stockOut } from "./helpers";

// Not a scene test: walks every page in fixture mode and saves a full-page
// screenshot at desktop and phone width, in the dark and the light theme, so a
// person can look at each one, and checks the visible text of each for machine
// words (helpers.slop). Files: ../../artifacts/shots/<page>-<width>-<theme>.png
const OUT = "../../artifacts/shots";

for (const theme of ["dark", "light"] as const) {
  test(`every page, both widths, ${theme}`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: theme });
    const problems: string[] = [];
    const go = (path: string) => page.goto(`${path}${path.includes("?") ? "&" : "?"}theme=${theme}`);
    async function shoot(name: string) {
      for (const width of [1280, 390]) {
        await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
        await page.waitForTimeout(200);
        await page.screenshot({ path: `${OUT}/${name}-${width}-${theme}.png`, fullPage: true });
        problems.push(...(await slop(page)).map((p) => `${name} ${width}: ${p}`));
      }
      await page.setViewportSize({ width: 1280, height: 900 });
    }

    await fresh(page);
    await go("/");
    await expect(page.getByTestId("inbox-R-1")).toContainText("Ordered alone");
    await shoot("inbox");

    await go("/requests/R-1");
    await expect(page.locator("#decision-sentence")).toContainText("Ordered 1,000 packs");
    await shoot("request-milk");
    await page.locator("#fold-options").click();
    await page.locator("#option-464306 .open").click();
    await page.locator("#option-463047").scrollIntoViewIfNeeded();
    await shoot("request-milk-open");

    await stockOut(page);
    await expect(page.locator("#request-title")).toContainText("200 bags");
    await shoot("request-mozzarella");

    await go("/approve/R-2");
    await expect(page.getByTestId("approve-question")).toContainText("180.10");
    await shoot("approve");
    await page.getByTestId("approve").click();
    await code(page);
    await expect(page.locator("#order-steps")).toContainText("Placed at Valio");
    await shoot("approve-done");

    await go("/steady");
    await shoot("steady-list");
    await go("/steady/S-1");
    await expect(page.locator("#simulated-history")).toBeVisible();
    await shoot("steady-before");
    await page.getByTestId("renew").click();
    await code(page);
    await expect(page.locator("#line-466375")).toContainText("26 %");
    await shoot("steady-renewed");

    await go("/spend-pass");
    await expect(page.locator("#pass-auto")).toContainText("1,200.00");
    await shoot("spend-pass");

    await go("/ledger");
    await expect(page.locator("#chain-status")).toContainText("Chain verified");
    await page.locator("#entry-8 .line").click();
    await shoot("ledger");
    expect(problems, problems.join("\n")).toEqual([]);
  });
}
