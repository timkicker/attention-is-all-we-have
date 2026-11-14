import { test, expect, type Page } from "@playwright/test";
import { CODE, fresh, slop } from "./helpers";

// Home in fixture mode: the first start checklist, then the agent and week
// line, Needs you and Latest, kept live after an answer.

async function newKitchen(page: Page) {
  await page.goto("/login");
  await page.evaluate(() => localStorage.clear());
  await page.getByTestId("login-swap").click();
  await page.getByTestId("login-kitchen").fill("School kitchen");
  await page.getByTestId("login-email").fill("chef@school.test");
  await page.getByTestId("login-password").fill("long enough");
  await page.getByTestId("login-customer").fill("123456");
  await page.getByTestId("login-code").fill("135790");
  await page.getByTestId("login-submit").click();
  await expect(page.locator("h1")).toHaveText("Home");
}

test("first start: three steps, each one a link", async ({ page }) => {
  await newKitchen(page);
  await expect(page.getByTestId("home-lead")).toContainText("School kitchen");
  await expect(page.getByTestId("setup-count")).toHaveText("0 of 3");
  await expect(page.getByTestId("home-status")).toHaveCount(0);
  await expect(page.getByTestId("section-needs")).toHaveCount(0);
  for (const [step, href] of [["rules", "/rules"], ["agent", "/agent"], ["order", "/activity"]]) {
    await expect(page.locator(`#step-${step}-go`)).toHaveAttribute("href", href);
  }
  await page.locator("#step-agent-go").click();
  await expect(page.locator("h1")).toHaveText("Agent");
});

test("set up: agent and week on one line, Needs you, Latest without repeats", async ({ page }) => {
  await fresh(page);
  await expect(page.getByTestId("section-setup")).toHaveCount(0);
  await expect(page.getByTestId("home-agent")).toContainText("Claude Code");
  await expect(page.getByTestId("home-agent")).toContainText("active");
  await expect(page.getByTestId("home-week")).toContainText("1,190.10");
  await expect(page.getByTestId("home-week")).toContainText("8,000.00");
  await expect(page.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "15");
  await expect(page.getByTestId("need-R-4")).toContainText("1,515.00");
  // R-4 waits: it is under Needs you and not again under Latest.
  await expect(page.getByTestId("section-latest").getByTestId("activity-R-4")).toHaveCount(0);
  await expect(page.getByTestId("section-latest").locator("a.ar")).toHaveCount(4);
  await expect(page.locator("#latest-link")).toHaveAttribute("href", "/activity");
  expect(await slop(page)).toEqual([]);
  await page.locator("#review-R-4").click();
  await expect(page).toHaveURL(/\/activity\/R-4$/);
});

test("after approving, Home updates on its own", async ({ page }) => {
  await fresh(page);
  await page.goto("/activity/R-4");
  await page.locator("#approve").click();
  await page.locator("#approve-code").fill(CODE);
  await page.getByTestId("code-submit").click();
  await expect(page.getByTestId("detail-status")).toHaveText("Ordered alone");
  await page.locator("#nav-home").click();
  await expect(page.getByTestId("needs-none")).toBeVisible();
  await expect(page.getByTestId("home-week")).toContainText("2,705.10");
  await expect(page.getByTestId("section-latest").getByTestId("activity-R-4")).toBeVisible();
  await expect(page.locator("#nav-home .nb")).toHaveCount(0);
});

test("phone: no sideways scroll on Home", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await fresh(page);
  await expect(page.getByTestId("need-R-4")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});
