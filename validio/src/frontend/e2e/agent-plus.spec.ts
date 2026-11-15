import { test, expect } from "@playwright/test";
import { fresh } from "./helpers";

// plans/025, Agent: the connection drawn in every state, and the steps while connecting.
test("the connection follows the agent from none to active", async ({ page }) => {
  await fresh(page);
  await page.goto("/agent");
  await expect(page.getByTestId("agent-link")).toHaveAttribute("data-state", "none");
  await expect(page.getByTestId("agent-steps")).toBeVisible();
  await page.locator("#agent-connect").click();
  await expect(page.getByTestId("agent-link")).toHaveAttribute("data-state", "pairing");
  await page.evaluate(() => (window as unknown as { validioMcpCall: () => void }).validioMcpCall());
  await expect(page.getByTestId("agent-link")).toHaveAttribute("data-state", "consent", { timeout: 5000 });
  await page.locator("#consent-allow").click();
  await expect(page.getByTestId("agent-link")).toHaveAttribute("data-state", "active");
  await expect(page.getByTestId("agent-steps")).toHaveCount(0);
  await expect(page.getByTestId("section-agent-recent")).toBeVisible();
});
