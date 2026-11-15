import { test, expect } from "@playwright/test";
import { fresh } from "./helpers";

// plans/025, F11: every page as a picture, at 1280 and 390 px in both themes, compared with the
// last approved one. Opt-in (the pictures are per platform): VISUAL=1 npx playwright test e2e/visual.spec.ts,
// and --update-snapshots after an intended change.
test.skip(!process.env.VISUAL, "visual regression is opt-in: VISUAL=1");

const PAGES = ["/", "/activity", "/activity/R-4", "/activity/R-1", "/rules", "/rules/edit", "/agent", "/settings"];
for (const [w, h] of [
  [1280, 900],
  [390, 844],
]) {
  for (const theme of ["light", "dark"]) {
    test(`pages at ${w} px, ${theme}`, async ({ page }) => {
      await page.setViewportSize({ width: w, height: h });
      await page.goto(`/login?theme=${theme}`);
      await expect(page).toHaveScreenshot(`login-${w}-${theme}.png`, { fullPage: true, animations: "disabled" });
      await fresh(page);
      for (const p of PAGES) {
        await page.goto(`${p}${p.includes("?") ? "&" : "?"}theme=${theme}`);
        await page.waitForLoadState("networkidle");
        await page.waitForTimeout(600);
        const name = p === "/" ? "home" : p.slice(1).replace(/\//g, "-");
        await expect(page).toHaveScreenshot(`${name}-${w}-${theme}.png`, { fullPage: true, animations: "disabled", maxDiffPixelRatio: 0.01 });
      }
    });
  }
}
