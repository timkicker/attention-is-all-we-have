import { test, expect } from "@playwright/test";
import { fresh } from "./helpers";

// The interactions the motion plans added (plans/010, 012, 013, 020, 021, 022). The suite runs with
// reduced motion, so nothing here waits on an animation.

test("⌘K opens the palette; typing and Enter go to the page", async ({ page }) => {
  await fresh(page);
  await page.keyboard.press("ControlOrMeta+k");
  const dlg = page.getByRole("dialog", { name: "Search and commands" });
  await expect(dlg).toBeVisible();
  await page.keyboard.type("Edit rules");
  await expect(dlg.locator('[data-slot="command-item"][data-selected]')).toHaveText(/Edit rules/);
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/rules\/edit$/);
  await expect(dlg).toBeHidden();
});

test("g then a goes to Activity; j moves to the first row; keys typed in a field stay there", async ({ page }) => {
  await fresh(page);
  await page.keyboard.press("g");
  await page.keyboard.press("a");
  await expect(page).toHaveURL(/\/activity$/);
  await expect(page.locator("a.ar").first()).toBeVisible();
  await page.keyboard.press("j");
  await expect(page.locator("a.ar").first()).toBeFocused();
  await page.keyboard.press("3");
  await expect(page).toHaveURL(/status=waiting/);
  await page.locator("#activity-find").fill("g a");
  await expect(page).toHaveURL(/status=waiting/);
});

test("Find narrows Activity, marks the words and Escape brings everything back", async ({ page }) => {
  await fresh(page);
  await page.goto("/activity");
  await expect(page.locator("a.ar").first()).toBeVisible();
  const all = await page.locator("a.ar").count();
  await page.locator("#activity-find").fill("mozz");
  await expect(page).toHaveURL(/q=mozz/);
  await expect(page.locator("a.ar mark").first()).toHaveText(/mozz/i);
  expect(await page.locator("a.ar").count()).toBeLessThan(all);
  await page.locator("#activity-find").press("Escape");
  await expect(page.locator("a.ar")).toHaveCount(all);
  await page.locator("#activity-find").fill("zzzz");
  await expect(page.getByText("Nothing matches")).toBeVisible();
});

test("Replay walks a request and opens its proof; Escape stops it", async ({ page }) => {
  await fresh(page);
  await page.goto("/activity/R-1");
  await page.getByTestId("replay").click();
  await expect(page.getByTestId("replay-status")).toHaveText("Replay finished", { timeout: 20_000 });
  await expect(page.locator("#proof")).toHaveAttribute("open", "");
  await page.getByTestId("replay").click();
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("replay-status")).toHaveText("Replay stopped");
});

test("the Rules scale's grips follow the arrow keys and fill the fields", async ({ page }) => {
  await fresh(page);
  await page.goto("/rules/edit");
  const grip = page.getByTestId("edit-scale-alone");
  await expect(grip).toHaveAttribute("aria-valuenow", "120000");
  await grip.focus();
  await page.keyboard.press("ArrowRight");
  await expect(grip).toHaveAttribute("aria-valuenow", "125000");
  await expect(page.locator("#f-alone")).toHaveValue("1,250.00");
  await page.keyboard.press("Shift+ArrowLeft");
  await expect(page.locator("#f-alone")).toHaveValue("750.00");
});

test("an approval made here raises no notification; the tab title counts what waits", async ({ page }) => {
  await fresh(page);
  await expect(page).toHaveTitle(/^\(1\) Validio$/);
  await page.goto("/activity/R-4");
  await page.locator("#approve").click();
  await page.locator("#approve-code").fill("246810");
  await page.getByTestId("code-submit").click();
  await expect(page.getByTestId("detail-status")).toHaveText("Approved by you");
  await expect(page).toHaveTitle("Validio");
  await page.waitForTimeout(2500);
  await expect(page.getByTestId("toast")).toHaveCount(0);
});
