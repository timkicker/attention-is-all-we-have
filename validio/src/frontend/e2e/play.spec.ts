import { test, expect } from "@playwright/test";
import { CODE, fresh, stockOut } from "./helpers";

// The play controls against the fixture: ask, change limits, stock-out on and off.

test("ask without a backend says so calmly", async ({ page }) => {
  await fresh(page);
  await page.locator("#page-menu").click();
  await page.getByTestId("menu-ask").click();
  await expect(page.getByTestId("ask-send")).toBeDisabled();
  const input = page.getByTestId("ask-input");
  await expect(input).toHaveAttribute("placeholder", "e.g. 50 kg of quark by Monday");
  await input.fill("500 litres of lactose-free milk by Monday");
  await input.press("Enter");
  // One muted line, the input cleared for the next ask, nothing raw.
  await expect(page.getByTestId("ask-entry")).toHaveCount(1);
  await expect(page.getByTestId("ask-none")).toContainText("no backend");
  // The one line is 13px muted, not larger than a row title.
  expect(await page.getByTestId("ask-none").evaluate((e) => getComputedStyle(e).fontSize)).toBe("13px");
  await expect(input).toHaveValue("");
  await expect(page.getByTestId("ask-log")).toHaveCount(0);
  await expect(page.getByRole("alert")).toHaveCount(0);
  // A chip sends at once; the newest row is on top.
  await page.locator("#ask-chip-3").click();
  await expect(page.getByTestId("ask-entry")).toHaveCount(2);
  // No footer: the ✕ closes it.
  const dialog = page.getByTestId("ask-dialog");
  await expect(dialog.getByRole("button", { name: "Close" })).toHaveCount(1);
  await expect(dialog.getByText("Recorded at Valio")).toHaveCount(0);
  const box = await dialog.boundingBox();
  expect(Math.round(box!.width)).toBeLessThanOrEqual(520);
  await dialog.getByRole("button", { name: "Close" }).click();
  await expect(dialog).toHaveCount(0);
});

test("dialogs: a plain dim over the whole width, and nothing pinned on top", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await fresh(page);
  await stockOut(page);
  await page.goto("/approve/R-2");
  const bar = page.locator("[data-bar]");
  await expect(bar).toBeVisible();
  await page.locator("#page-menu").click();
  await expect(page.locator("#menu-ask")).toBeVisible();
  await expect(bar).toBeHidden();
  const scrim = page.locator(".dialog-backdrop");
  expect(await scrim.evaluate((e) => getComputedStyle(e).backdropFilter)).toBe("none");
  const w = await scrim.evaluate((e) => e.getBoundingClientRect().width);
  expect(w).toBe(await page.evaluate(() => window.innerWidth));
  // The sheet's first item is hit where it is drawn, not the bar's button.
  const item = await page.locator("#menu-ask").boundingBox();
  const hit = await page.evaluate(([x, y]) => document.elementFromPoint(x, y)?.closest("[id]")?.id, [item!.x + 20, item!.y + item!.height / 2]);
  expect(hit).toBe("menu-ask");
  await page.keyboard.press("Escape");
  await expect(bar).toBeVisible();
});

test("the stock-out switch turns off again", async ({ page }) => {
  await fresh(page);
  await stockOut(page);
  await expect(page.getByTestId("inbox-R-2")).toBeVisible();
  await page.locator("#page-menu").click();
  await expect(page.getByText("Demo", { exact: true })).toBeVisible();
  await expect(page.getByTestId("stock-out")).toHaveAttribute("aria-checked", "true");
  await page.getByTestId("stock-out").click();
  await page.locator("#page-menu").click();
  await expect(page.getByTestId("stock-out")).toHaveAttribute("aria-checked", "false");
  await page.keyboard.press("Escape");
  // What the agent already asked for stays where it was.
  await expect(page.getByTestId("inbox-R-2")).toBeVisible();
});

// The public link: every write needs the presenter's token. The first write asks for it once,
// a wrong one asks again, then the write runs; later writes send it without asking.
test("on the public link every write asks for the demo token once", async ({ page }) => {
  await fresh(page);
  await page.evaluate(() => localStorage.setItem("validio-mock-public", "pub-token"));
  await page.goto("/steady/S-1");
  await page.getByTestId("renew").click();
  if (await page.getByTestId("code-input").isVisible({ timeout: 2000 }).catch(() => false)) {
    await page.getByTestId("code-input").fill(CODE);
    await page.getByTestId("code-submit").click();
  }
  const token = page.locator("#demo-token-input");
  await expect(token).toBeVisible();
  await expect(page.getByRole("dialog")).toContainText("Demo token");
  await token.fill("wrong");
  await page.getByRole("button", { name: "Run", exact: true }).click();
  await expect(page.getByTestId("token-problem")).toHaveText("That token is not right.");
  // The typed value stays, so it can be corrected.
  await expect(token).toHaveValue("wrong");
  await token.fill("pub-token");
  await page.getByRole("button", { name: "Run", exact: true }).click();
  await expect(page.getByTestId("line-463968")).toContainText("772.49");

  // The same page session (the token lives in memory): the stock-out switch and approve send it without asking.
  await page.locator("#nav-inbox").click();
  await page.locator("#page-menu").click();
  await page.getByTestId("stock-out").click();
  await expect(page.getByTestId("inbox-R-2")).toBeVisible();
  await expect(token).toHaveCount(0);
  await page.getByTestId("inbox-R-2").click();
  await page.locator("#open-approve").click();
  await page.getByTestId("approve").click();
  if (await page.getByTestId("code-input").isVisible({ timeout: 2000 }).catch(() => false)) {
    await page.getByTestId("code-input").fill(CODE);
    await page.getByTestId("code-submit").click();
  }
  await expect(page.locator("#order-done")).toBeVisible();
  await expect(token).toHaveCount(0);
});

test("closing the token dialog sends nothing and shows no error", async ({ page }) => {
  await fresh(page);
  await page.evaluate(() => localStorage.setItem("validio-mock-public", "pub-token"));
  await page.locator("#page-menu").click();
  await page.getByTestId("stock-out").click();
  await expect(page.locator("#demo-token-input")).toBeVisible();
  await page.getByRole("button", { name: "Cancel" }).click();
  await expect(page.locator("#demo-token-input")).toHaveCount(0);
  await expect(page.getByRole("alert")).toHaveCount(0);
  await expect(page.getByTestId("inbox-R-2")).toHaveCount(0);
});

test("Reset in the phone's demo bar starts over in one step", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await fresh(page);
  await stockOut(page);
  await expect(page.getByTestId("inbox-R-2")).toBeVisible();
  await page.locator("#demo-reset").click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByTestId("inbox-R-2")).toHaveCount(0);
});

test("the ledger heads: Demo without an id, every id once", async ({ page }) => {
  await fresh(page);
  await stockOut(page);
  await page.goto("/ledger");
  await expect(page.getByTestId("ledger-group-demo")).toHaveText(/^Demo$/);
  for (const head of await page.locator("[data-testid^=ledger-group-]").allInnerTexts()) {
    const id = head.match(/\b[RSM]-\d+\b/g) ?? [];
    expect(id.length, head).toBeLessThanOrEqual(1);
  }
});

