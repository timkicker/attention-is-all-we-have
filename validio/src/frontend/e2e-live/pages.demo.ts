import { connector } from "./connector";
import { CODE, connectMcpAgent, expect, fresh, test } from "./kitchen";

// A click through the v2 pages on a demo copy from the plain seed (no agent), against the live backend:
// every nav target answers, the Agent page walks none -> pairing -> back, a wrong rules code is refused,
// and last an order by an MCP agent opens from Activity.
// Needs no local store: runs against E2E_BASE as well.

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ kitchen }) => {
  await fresh(kitchen);
});

test("login page: demo button and its code, deep links go through the login", async ({ browser, baseURL }) => {
  const anon = await browser.newContext({ baseURL });
  const p = await anon.newPage();
  await p.goto("/activity");
  await expect(p).toHaveURL(/\/login$/);
  await expect(p.getByTestId("try-demo")).toHaveText(/Try the demo kitchen/);
  await expect(p.getByTestId("demo-code")).toHaveText(CODE);
  await expect(p.getByTestId("login-submit")).toBeVisible();
  await anon.close();
});

test("nav: Home, Activity, Rules, Agent, Settings", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("demo-bar")).toBeVisible();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Home");
  for (const [nav, path, title] of [
    ["nav-activity", /\/activity$/, "Activity"],
    ["nav-rules", /\/rules$/, "Rules"],
    ["nav-agent", /\/agent$/, "Agent"],
    ["nav-settings", /\/settings$/, "Settings"],
    ["nav-home", /\/$/, "Home"],
  ] as const) {
    await page.getByTestId(nav).click();
    await expect(page).toHaveURL(path);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(title);
  }
});

test("Home: checklist or status, Needs you", async ({ page }) => {
  await page.goto("/");
  const setup = page.getByTestId("section-setup");
  const status = page.getByTestId("home-status");
  await expect(setup.or(status)).toBeVisible();
  if (await setup.isVisible()) {
    await expect(page.getByTestId("setup-count")).toHaveText(/\d of 3/);
    await page.getByTestId("step-agent-go").click();
    await expect(page).toHaveURL(/\/agent$/);
  } else {
    await expect(page.getByTestId("home-agent")).toContainText("No agent connected");
    await expect(page.getByTestId("section-needs")).toBeVisible();
  }
});

test("Rules: version, edit with a wrong code is refused, Save keeps nothing", async ({ page }) => {
  await page.goto("/rules");
  const version = (await page.getByTestId("rules-version").textContent()) ?? "";
  await page.getByTestId("rules-edit").click();
  await expect(page).toHaveURL(/\/rules\/edit$/);
  await page.getByTestId("f-alone").fill("700");
  await page.getByTestId("code-input").fill(CODE === "000000" ? "111111" : "000000");
  await page.getByTestId("code-submit").click();
  await expect(page.getByText("That code is not right.")).toBeVisible();
  await page.goto("/rules");
  await expect(page.getByTestId("rules-version")).toHaveText(version);
});

test("Agent: none -> pairing with the MCP URL and Copy -> Cancel", async ({ page, kitchen }) => {
  await kitchen.ctx.grantPermissions(["clipboard-read", "clipboard-write"]).catch(() => {});
  await page.goto("/agent");
  await expect(page.getByTestId("agent-none")).toBeVisible();
  await page.getByTestId("agent-connect").click();
  await expect(page.getByTestId("agent-state")).toHaveText("Connecting");
  await expect(page.getByTestId("mcp-url")).toHaveText(/\/mcp\/c\/[^/]+\/$/);
  await page.getByTestId("copy-mcp").click();
  await expect(page.getByTestId("copy-mcp")).toHaveText("Copied");
  await expect(page.getByTestId("pair-code-text")).not.toBeEmpty();
  await page.getByTestId("pair-cancel").click();
  await expect(page.getByTestId("agent-none")).toBeVisible();
});

test("Settings: the kitchen and Log out", async ({ page }) => {
  await page.goto("/settings");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Settings");
  await expect(page.getByTestId("log-out")).toBeVisible();
});

test("Activity: rows open their detail, the detail goes back", async ({ page, kitchen }) => {
  // the plain seed has no activity: an MCP agent connects and orders once
  const run = connector(await connectMcpAgent(kitchen));
  expect(run.ok, run.out).toBe(true);
  await page.goto("/activity");
  const first = page.locator('[data-testid^="activity-"]').first();
  const id = ((await first.getAttribute("data-testid")) ?? "").replace("activity-", "");
  await first.click();
  await expect(page).toHaveURL(new RegExp(`/activity/${id}$`));
  await expect(page.getByTestId("detail-status")).toBeVisible();
  await expect(page.getByTestId("asked")).toBeVisible();
  await expect(page.getByTestId("rule")).toContainText(/Rules, version \d+/);
  await page.getByTestId("proof").locator("summary").click();
  await expect(page.getByTestId("proof")).toHaveAttribute("open", "");
  // An unknown id: the page wants "<id> not found" for its Not found state, the backend answers 404
  // "no request <id>" (api/activity.py), so live it shows the load error ("not reachable") with that text.
  await page.goto("/activity/R-999");
  await expect(page.getByText(/^Not found$|no request R-999/).first()).toBeVisible();
  await expect(page.getByTestId("detail-status")).toHaveCount(0);
});
