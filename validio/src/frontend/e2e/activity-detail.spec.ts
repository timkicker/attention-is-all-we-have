import { test, expect } from "@playwright/test";
import { CODE, fresh, slop } from "./helpers";

// One request top to bottom, and the answer given in place.

test("an ordered request reads asked, checked, rule, result, proof", async ({ page }) => {
  await fresh(page);
  await page.goto("/activity/R-2");
  await expect(page.getByTestId("detail-title")).toHaveText(/mozzarella-fontal/);
  await expect(page.getByTestId("detail-status")).toHaveText("Auto-ordered");
  await expect(page.getByTestId("asked")).toContainText("Kitchen agent");
  await expect(page.getByTestId("check-stock")).toHaveAttribute("data-ok", "false");
  await expect(page.getByTestId("check-substitute")).toHaveAttribute("data-ok", "true");
  await expect(page.locator("#rule-link")).toHaveAttribute("href", "/rules");
  await expect(page.getByTestId("rule-version")).toHaveText("Rules, version 2");
  await expect(page.getByTestId("result-order")).toHaveAttribute("data-order", "O-6");
  await expect(page.getByTestId("result-delivery")).toContainText("Mon 16 Nov");
  await expect(page.getByTestId("approval")).toHaveCount(0);
  // Proof is folded until asked for.
  await expect(page.locator("#proof .pe").first()).toBeHidden();
  await page.locator("#proof-toggle").click();
  await expect(page.locator("#proof .pe")).toHaveCount(3);
  expect(await slop(page)).toEqual([]);
});

test("waiting: Approve asks the code in place of the buttons, Cancel brings them back", async ({ page }) => {
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
  await expect(page.getByTestId("result-order")).toHaveAttribute("data-order", "O-7");
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

test("many items: one order table with a total, checks folded under each row, the left-out line says why", async ({ page }) => {
  await fresh(page);
  await page.goto("/activity/R-5");
  await expect(page.getByTestId("detail-title")).toHaveText("9 items: butternut squash, onion, garlic and 6 more");
  await expect(page.getByTestId("detail-lede")).toHaveText(
    "Auto-ordered 8 of 9 items. 82.19 €, arriving Fri 20 Nov. 1 item couldn't be delivered in time.",
  );
  const table = page.getByTestId("order-lines");
  await expect(table.locator("tr.row")).toHaveCount(9);
  await expect(page.getByTestId("lines-total")).toContainText("82.19");
  await expect(page.getByTestId("lines-total")).toContainText("8 of 9 items");
  // No stacked check blocks and no empty comparison.
  await expect(page.getByTestId("check-product")).toHaveCount(0);
  await expect(page.getByTestId("options")).toHaveCount(0);
  await expect(page.getByText("No product fitted every rule")).toHaveCount(0);
  // The left-out line: its reason in plain words and the order that brought it later.
  const late = page.getByTestId("line-L9");
  await expect(late).toHaveAttribute("data-ordered", "false");
  await expect(late.getByTestId("line-reason")).toContainText("Can't be delivered by Fri 20 Nov");
  await expect(late).toContainText("Not ordered");
  await expect(late.getByTestId("line-replaced")).toHaveAttribute("href", "/activity/R-6");
  // A row opens to its checks.
  await expect(page.locator("#checks-L1")).toBeHidden();
  await page.getByTestId("line-L1").getByRole("button").click();
  await expect(page.locator("#checks-L1")).toBeVisible();
  await expect(page.locator("#checks-L1")).toContainText("1.49 € per kg");
  await expect(page.getByTestId("line-L1").getByRole("button")).toHaveAttribute("aria-expanded", "true");
  expect(await slop(page)).toEqual([]);
  // The replacement link goes to the agent's next request.
  await late.getByTestId("line-replaced").click();
  await expect(page).toHaveURL(/\/activity\/R-6$/);
});

test("many items, phone: rows fold into name, quantity at the unit price and total, no sideways scroll", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await fresh(page);
  await page.goto("/activity/R-5");
  await expect(page.getByTestId("line-L2").locator(".meta")).toHaveText("2 × 1 kg at 1.45 €, arrives Fri 20 Nov");
  await expect(page.getByTestId("order-lines").locator("thead")).toBeHidden();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});
