import { execFileSync } from "node:child_process";
import { test, expect } from "@playwright/test";

// The built web app and the API from one process, no Vite: the real agent places requests over
// MCP, the pages read them through /api on the same origin.
function agent(scene: number) {
  execFileSync("uv", ["run", "python", "-W", "ignore", "../../scripts/agent.py", "--scene", String(scene),
    "--base", process.env.SMOKE_BASE!], {
    cwd: "../backend",
    env: process.env,
    stdio: "pipe",
  });
}

test.describe.configure({ mode: "serial" });

test("app and API from one process", async ({ page, request }) => {
  expect((await request.get("/api/health")).status()).toBe(200);
  expect((await request.get("/api/nope")).status()).toBe(404);
  // a deep link is the SPA's index.html, not a 404
  const deep = await request.get("/requests/R-9");
  expect(deep.status()).toBe(200);
  expect(await deep.text()).toContain("<html");

  await request.post("/api/demo/reset");
  agent(2);
  await page.goto("/");
  await expect(page.locator("#inbox-R-1")).toContainText("Ordered alone");
  await page.locator("#inbox-R-1").click();
  await expect(page).toHaveURL(/\/requests\/R-1$/);
  await expect(page.locator("#decision-sentence")).toContainText("Ordered 1,000 packs of Valio");
  await expect(page.locator("#live-checked")).toContainText("Checked 12 products live");
  await expect(page.locator("#option-464306")).toContainText("1,010.00");
  await expect(page.locator("#option-462921")).toContainText("hard cap");
  await page.reload(); // served by FastAPI's fallback
  await expect(page.locator("#decision-sentence")).toContainText("Ordered 1,000 packs of Valio");
});

test("owner approves the swap on the phone", async ({ page }) => {
  await page.goto("/");
  await page.locator("#stock-out").click();
  await expect(page.locator("#stock-out")).toBeVisible();
  agent(3);
  await page.reload();
  await expect(page.locator("#inbox-R-2")).toContainText("Waiting for you");
  await page.locator("#inbox-R-2").click();
  await expect(page.locator("#option-473986")).toContainText("Not deliverable");
  await expect(page.locator("#option-465256")).toContainText("180.10");

  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator("#open-approve").click();
  await page.locator("#approve").click();
  // the app asks for the code; this server has none set and takes any code from this machine
  await page.getByTestId("code-input").fill("246810");
  await page.getByTestId("code-submit").click();
  await expect(page.locator("#order-steps")).toContainText("Placed at Valio");

  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/ledger");
  await expect(page.locator("#chain-status")).toContainText("Chain verified");
  await expect(page.locator("#ledger")).toContainText("after the owner approved");
});
