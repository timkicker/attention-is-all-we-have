import { test, expect, type Page } from "@playwright/test";

// Every page against the real backend, with the approval code and the demo
// token switched on. A page error of any kind fails the run: the pages must
// render whatever the API answers.
const CODE = process.env.LIVE_CODE ?? "135790";
const TOKEN = process.env.LIVE_TOKEN ?? "live-run-token";

function watch(page: Page): string[] {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => {
    if (m.type() === "error" && !m.text().includes("status of 40")) errors.push(m.text());
  });
  return errors;
}

test("live: scenes 2 to 5 against the backend", async ({ page }) => {
  const errors = watch(page);

  // Scene 2, as the backend left it.
  await page.goto("/");
  await expect(page.locator("#inbox-R-1")).toContainText("Ordered alone");
  await page.locator("#inbox-R-1").click();
  await expect(page.locator("#request-status")).toContainText("Ordered alone");
  await expect(page.locator("#live-checked")).toContainText("Live");
  await expect(page.locator("#option-462921")).toContainText("hard cap");
  await page.locator("#fold-options").click();
  await expect(page.locator("#reader-463047")).toContainText("Order all 132 in stock");
  await expect(page.locator("#spend-pass")).toContainText("1,200.00");

  // Scene 3: the owner approves on the phone; the backend wants the code.
  await page.locator("#inbox-R-2").click();
  await expect(page.locator("#option-465256")).toContainText("Chosen");
  await expect(page.locator("#simulated-stock-out")).toContainText("only in this demo");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator("#open-approve").click();
  await expect(page.locator("#question")).toContainText("Order 10 × 2.5 kg of mozzarella-fontal crumbled cheese");
  await page.locator("#approve-code").fill("000000");
  await page.locator("#approve").click();
  await expect(page.locator("#code-help")).toContainText("not right");
  await page.locator("#approve-code").fill(CODE);
  await page.locator("#approve").click();
  await expect(page.locator("#order-done")).toContainText("confirmed again");
  await page.setViewportSize({ width: 1280, height: 900 });

  // Scene 4: renew and accept send the code typed once above (same session).
  await page.locator("#nav-steady-orders").click();
  await page.getByRole("link", { name: /Weekly Monday order/ }).click();
  await expect(page.locator("#simulated-history")).toContainText("simulated");
  await page.locator("#renew").click();
  await expect(page.locator("#line-463968")).toContainText("772.49");
  await expect(page.locator("#line-466375")).toContainText("None in stock at Valio.");
  await page.locator("#accept-471376").click();
  await expect(page.locator("#line-471376")).toContainText("Accepted");

  // Scene 5 and the Spend Pass.
  await page.locator("#nav-open-ledger").click();
  await expect(page.locator("#chain-status")).toContainText("Chain verified");
  await expect(page.locator("#ledger")).toContainText("Owner approved 10 × 2.5 kg of mozzarella-fontal crumbled cheese");
  await expect(page.locator("#ledger")).not.toContainText("owner:anna");
  await page.locator("#nav-spend-pass").click();
  await expect(page.locator("#pass-auto")).toContainText("1,200.00");

  // The demo switches want the presenter's token: asked in a dialog, then run.
  await page.locator("#page-menu").click();
  await page.locator("#reset").click();
  await page.locator("#demo-token-input").fill(TOKEN);
  await page.getByRole("button", { name: "Use and run" }).click();
  await expect(page.locator("#inbox-R-1")).toHaveCount(0);
  await page.locator("#nav-open-ledger").click();
  await expect(page.locator("#chain-status")).toContainText("Chain verified");

  expect(errors).toEqual([]);
});
