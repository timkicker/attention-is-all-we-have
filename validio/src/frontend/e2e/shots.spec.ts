import { test, expect, type Page } from "@playwright/test";
import { code, fresh, slop, stockOut } from "./helpers";

// Not a scene test: walks every page in fixture mode and saves a full-page
// screenshot at each width and theme below, so a person can look at each one,
// and checks the visible text of each for machine words (helpers.slop).
// Files: $SHOTS (default ../../artifacts/shots)/<page>-<width>-<theme>.png
const OUT = process.env.SHOTS ?? "../../artifacts/shots";
const VIEWS = [
  { width: 1280, height: 900, theme: "light" },
  { width: 1280, height: 900, theme: "dark" },
  { width: 390, height: 844, theme: "light" },
  { width: 900, height: 900, theme: "light" },
  { width: 1600, height: 1000, theme: "light" },
] as const;

for (const v of VIEWS) {
  test(`every page, ${v.width} ${v.theme}`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: v.theme });
    await page.setViewportSize({ width: v.width, height: v.height });
    const problems: string[] = [];
    const go = (path: string) => page.goto(`${path}${path.includes("?") ? "&" : "?"}theme=${v.theme}`);
    async function shoot(name: string, p: Page = page) {
      await p.waitForTimeout(250);
      await p.screenshot({ path: `${OUT}/${name}-${v.width}-${v.theme}.png`, fullPage: true });
      problems.push(...(await slop(p)).map((x) => `${name}: ${x}`));
    }

    await fresh(page);
    await go("/");
    await expect(page.getByTestId("inbox-R-1")).toContainText("Ordered alone");
    await shoot("inbox");

    await go("/requests/R-1");
    await expect(page.locator("#decision-sentence")).toContainText("Ordered 1,000 × 1 l");
    await shoot("request-r1");
    await stockOut(page);
    await go("/");
    await expect(page.getByTestId("inbox-R-2")).toContainText("Waiting for you");
    await shoot("inbox-waiting");
    await go("/requests/R-2");
    await expect(page.locator("#request-title")).toContainText("200 bags");
    await shoot("request-r2");

    await go("/approve/R-2");
    await expect(page.getByTestId("approve-question")).toContainText("180.10");
    await shoot("approve");
    if (v.width === 1280) {
      // The focus mark: a keyboard Tab, then the outline button.
      await page.keyboard.press("Tab");
      await page.getByTestId("reject").focus();
      await expect(page.getByTestId("reject")).toBeFocused();
      await page.waitForTimeout(150);
      await page.screenshot({ path: `${OUT}/focus-${v.width}-${v.theme}.png` });
    }
    await page.getByTestId("approve").click();
    await expect(page.getByTestId("code-input")).toBeFocused();
    await shoot("approve-code");
    await code(page);
    await expect(page.locator("#order-steps")).toContainText("Validio placed the order");
    await shoot("approve-done");

    await go("/steady");
    await expect(page.getByTestId("steady-S-1")).toBeVisible();
    await shoot("steady-list");
    await go("/steady/S-1");
    await expect(page.locator("#simulated-history")).toBeAttached();
    await shoot("steady-before");
    await page.getByTestId("renew").click();
    await code(page);
    await expect(page.locator("#line-466375")).toContainText("26 %");
    await shoot("steady-renewed");

    await go("/spend-pass");
    await expect(page.locator("#pass-auto")).toContainText("1,200.00");
    await shoot("spend-pass");

    await go("/ledger");
    await expect(page.locator("#chain-status")).toContainText("Verified");
    await shoot("ledger");

    // The other ending: the owner rejects R-2.
    await fresh(page);
    await stockOut(page);
    await go("/approve/R-2");
    await page.getByTestId("reject").click();
    await code(page);
    await expect(page.locator("#order-steps")).toContainText("You rejected");
    await shoot("approve-rejected");
    await go("/requests/R-2");
    await expect(page.getByTestId("request-status")).toContainText("Rejected");
    await shoot("request-rejected");
    expect(problems, problems.join("\n")).toEqual([]);
  });
}
