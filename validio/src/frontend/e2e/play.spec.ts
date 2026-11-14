import { test, expect } from "@playwright/test";
import { CODE, fresh, stockOut } from "./helpers";

// The demo controls against the fixture: the token dialog, the public link, Reset.

test("dialogs: a plain dim over the whole width, and nothing pinned on top", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await fresh(page);
  await stockOut(page);
  // On the public link the approve asks for the token: that dialog over the approve page's bar.
  await page.evaluate(() => localStorage.setItem("validio-mock-public", "pub-token"));
  await page.goto("/approve/R-2");
  const bar = page.locator("[data-bar]");
  await expect(bar).toBeVisible();
  await page.getByTestId("approve").click();
  if (await page.getByTestId("code-input").isVisible({ timeout: 2000 }).catch(() => false)) {
    await page.getByTestId("code-input").fill(CODE);
    await page.getByTestId("code-submit").click();
  }
  const token = page.locator("#demo-token-input");
  await expect(token).toBeVisible();
  const scrim = page.locator(".dialog-backdrop");
  expect(await scrim.evaluate((e) => getComputedStyle(e).backdropFilter)).toBe("none");
  const w = await scrim.evaluate((e) => e.getBoundingClientRect().width);
  expect(w).toBe(await page.evaluate(() => window.innerWidth));
  // The field is hit where it is drawn, not anything under the dim.
  const box = await token.boundingBox();
  const hit = await page.evaluate(([x, y]) => document.elementFromPoint(x, y)?.closest("[id]")?.id, [box!.x + 20, box!.y + box!.height / 2]);
  expect(hit).toBe("demo-token-input");
  await page.keyboard.press("Escape");
  await expect(token).toHaveCount(0);
  await expect(bar).toBeVisible();
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

  // The same page session (the token lives in memory): approve sends it without asking.
  await page.evaluate(() => {
    const k = "validio-mock-v2";
    const st = JSON.parse(localStorage.getItem(k)!);
    localStorage.setItem(k, JSON.stringify({ ...st, moz: "waiting" }));
  });
  await page.locator("#nav-inbox").click();
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
  await stockOut(page);
  await page.evaluate(() => localStorage.setItem("validio-mock-public", "pub-token"));
  await page.locator("#demo-reset").click();
  await expect(page.locator("#demo-token-input")).toBeVisible();
  await page.getByRole("button", { name: "Cancel" }).click();
  await expect(page.locator("#demo-token-input")).toHaveCount(0);
  await expect(page.getByRole("alert")).toHaveCount(0);
  // Nothing was reset: the waiting request is still there.
  await expect(page.getByTestId("inbox-R-2")).toBeVisible();
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

