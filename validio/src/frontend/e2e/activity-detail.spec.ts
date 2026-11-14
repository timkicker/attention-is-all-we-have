import { test, expect } from "@playwright/test";
import { CODE, fresh, slop } from "./helpers";

// One request top to bottom, and the answer given in place.

test("an ordered request reads asked, checked, rule, result, proof", async ({ page }) => {
  await fresh(page);
  await page.goto("/activity/R-2");
  await expect(page.getByTestId("detail-title")).toHaveText(/mozzarella-fontal/);
  await expect(page.getByTestId("detail-status")).toHaveText("Ordered alone");
  await expect(page.getByTestId("asked")).toContainText("Claude Code");
  await expect(page.getByTestId("check-stock")).toHaveAttribute("data-ok", "false");
  await expect(page.getByTestId("check-substitute")).toHaveAttribute("data-ok", "true");
  await expect(page.locator("#rule-link")).toHaveAttribute("href", "/rules");
  await expect(page.locator("#rule-link")).toContainText("Rules, version 4");
  await expect(page.getByTestId("result-order")).toContainText("O-6");
  await expect(page.getByTestId("result-delivery")).toContainText("Mon 16 Nov");
  await expect(page.getByTestId("approval")).toHaveCount(0);
  // Proof is folded until asked for.
  await expect(page.locator("#proof .pe").first()).toBeHidden();
  await page.locator("#proof-toggle").click();
  await expect(page.locator("#proof .pe")).toHaveCount(3);
  expect(await slop(page)).toEqual([]);
});

test("waiting: Approve asks the code under the buttons, Cancel closes it", async ({ page }) => {
  await fresh(page);
  await page.goto("/activity/R-4");
  await expect(page.getByTestId("approval")).toContainText("15:00 today");
  await expect(page.getByTestId("result-none")).toHaveText("Not ordered yet");
  await expect(page.locator("#approve-code")).toHaveCount(0);
  await page.locator("#approve").click();
  await expect(page.locator("#approve-code")).toBeFocused();
  await page.getByRole("button", { name: "Cancel" }).click();
  await expect(page.locator("#approve-code")).toHaveCount(0);
  await expect(page.locator("#approve")).toBeFocused();
});

test("a short code is refused, six digits approve and the page updates", async ({ page }) => {
  await fresh(page);
  await page.goto("/activity/R-4");
  await page.locator("#approve").click();
  await page.locator("#approve-code").fill("12");
  await page.getByTestId("code-submit").click();
  await expect(page.getByText("The code has 6 digits")).toBeVisible();
  await page.locator("#approve-code").fill(CODE);
  await page.getByTestId("code-submit").click();
  await expect(page.getByTestId("approval")).toHaveCount(0);
  await expect(page.getByTestId("detail-status")).not.toHaveText("Waiting for you");
  await expect(page.getByTestId("result-order")).toContainText("O-7");
  await expect(page.locator("#nav-home .nb")).toHaveCount(0);
});

test("Reject needs no code and blocks the request", async ({ page }) => {
  await fresh(page);
  await page.goto("/activity/R-4");
  await page.locator("#reject").click();
  await expect(page.getByTestId("detail-status")).toHaveText("Blocked");
  await expect(page.getByTestId("approval")).toHaveCount(0);
  await expect(page.getByTestId("result-none")).toHaveText("Nothing ordered");
});

test("an unknown id says so", async ({ page }) => {
  await fresh(page);
  await page.goto("/activity/R-99");
  await expect(page.getByText("Not found")).toBeVisible();
});

test("phone: the code line fits, no sideways scroll", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await fresh(page);
  await page.goto("/activity/R-4");
  await page.locator("#approve").click();
  const field = await page.locator("#approve-code").boundingBox();
  const confirm = await page.getByTestId("code-submit").boundingBox();
  expect(Math.abs((field?.y ?? 0) - (confirm?.y ?? 99))).toBeLessThan(8);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});
