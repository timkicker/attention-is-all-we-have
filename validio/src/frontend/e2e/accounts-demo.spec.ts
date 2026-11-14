import { test, expect, type Page, type Locator } from "@playwright/test";
import { CODE } from "./helpers";
import { connectMcp, connector } from "../e2e-live/connector";

// "Done means" of the accounts plan, clicked in a fresh browser: try the demo kitchen, connect an MCP
// agent (scripts/connector_check.py on the page's URL, the verification codes compared), let it order
// milk and see it ordered, lower the alone limit in Rules with the code, send
// again and see it wait, approve with the code, pause the agent and see the refusal in the ledger, change
// the diet in Settings. A second browser holds its own demo copy and must not see any of it.
//
// Against the real backend only (the mock web app of the default config skips it):
//   npx playwright test -c playwright.accounts.config.ts       its own server, fresh template
//   ACCOUNTS_BASE=https://... npx playwright test e2e/accounts-demo.spec.ts   a running server or the public link
//
// Numbers: the demo template (alone up to 1,200.00 €, the example 1,010.00 €), lowered to 800 €.
const BASE = process.env.ACCOUNTS_BASE;
if (BASE) test.use({ baseURL: BASE });

/** A control by its test id, or else by its role and visible label (the labels in docs/DEMO.md). */
function el(page: Page, id: string | RegExp, role: "button" | "link" | "tab" | "checkbox" | "textbox", name: RegExp): Locator {
  return page.getByTestId(id).or(page.getByRole(role, { name })).filter({ visible: true }).first();
}

async function freshDemo(page: Page) {
  await page.goto("/login");
  await page.evaluate(() => localStorage.clear());
  await page.context().clearCookies();
  await page.goto("/login");
  await el(page, "try-demo", "button", /try the demo kitchen/i).click();
  await expect(page).not.toHaveURL(/\/login/);
}

const nav = (page: Page, id: string, name: RegExp) => el(page, id, "link", name);

/** Type the code when the page asks for it (a page that remembers it this visit does not), then submit. */
async function typeCode(page: Page) {
  const box = page.getByTestId("code-input").filter({ visible: true }).first();
  if (await box.waitFor({ timeout: 3_000 }).then(() => true, () => false)) await box.fill(CODE);
  await page.getByTestId("code-submit").filter({ visible: true }).first().click();
}

/** The MCP agent orders the milk; the Inbox (or Orders, for a handled one) has one more row with
 * `status` than before (the template's own scenes already have rows like it). */
async function agentOrders(page: Page, url: string, status: RegExp, where: "inbox" | "orders") {
  await (where === "inbox" ? nav(page, "nav-inbox", /^inbox$/i) : nav(page, "nav-orders", /^orders$/i)).click();
  await page.waitForLoadState("networkidle");
  const rows = page.locator("main").getByText(status);
  const before = await rows.count();
  connector(url);
  await expect(async () => {
    await page.reload();
    await expect(rows).toHaveCount(before + 1, { timeout: 2_000 });
  }).toPass({ timeout: 30_000 });
}

test("the demo path, end to end, in a fresh browser", async ({ page, browser }) => {
  test.skip(!BASE, "runs against a server: -c playwright.accounts.config.ts or ACCOUNTS_BASE");
  test.setTimeout(180_000);
  await freshDemo(page);
  const agentNav = nav(page, "nav-agent", /^agent$/i);
  const connect = el(page, "agent-connect", "button", /^connect agent$/i);
  if (await agentNav.count()) await agentNav.click();
  const built = await connect.waitFor({ timeout: 5_000 }).then(() => true, () => false);
  test.skip(!built, "the Agent page with Connect agent is not built yet");
  await nav(page, "nav-inbox", /^inbox$/i).click();

  // the demo bar names the code on purpose
  await expect(page.getByText(CODE).first()).toBeVisible();

  // a second browser with its own copy, opened before A acts
  const other = await browser.newContext({ baseURL: BASE ?? test.info().project.use.baseURL });
  const b = await other.newPage();
  await freshDemo(b);
  await nav(b, "nav-inbox", /^inbox$/i).click();
  const bInbox = await b.locator("main").innerText();

  // 2 connect an MCP agent: its first call asks, the page and the agent show the same code, Allow
  const url = await connectMcp(page);

  // 3 the agent orders the milk alone (a handled request is in Orders, not the Inbox)
  await agentOrders(page, url, /ordered alone/i, "orders");
  await expect(page.getByText("1,010.00 €").first()).toBeVisible();

  // 4 lower the alone limit in Rules, with the code
  await agentNav.click();
  await el(page, "rules-edit", "button", /^(edit|set rules)$/i).click();
  await page.getByTestId("r-alone").fill("800");
  await typeCode(page);
  await expect(page.getByTestId("rules-alone")).toContainText("800.00 €");

  // 5 the same request again waits
  await agentOrders(page, url, /waiting for you/i, "inbox");
  const waiting = page.locator("main").getByText(/waiting for you/i).first();
  // the request waits; it is not blocked (the inbox facts still name the "blocked above" limit)
  await expect(page.locator("main").getByText(/blocked(?! above)/i)).toHaveCount(0);

  // 6 approve with the code
  await waiting.click();
  await el(page, "open-approve", "link", /open approval/i).click();
  await el(page, "approve", "button", /^approve$/i).click();
  // every approval asks for the code, also when Rules took it this visit; the demo bar shows it here
  await expect(page.locator("#code-help")).toContainText("246810");
  await expect(page.getByTestId("approve-why")).toHaveText(/over your 800\.00\s€ limit for ordering alone/i);
  await expect(page.getByTestId("code-input")).toBeVisible();
  await typeCode(page);
  await expect(page.getByText(/^(placed|ordered)$/i).filter({ visible: true }).first()).toBeVisible({ timeout: 30_000 });

  // 7 pause, the agent asks again, the refusal stands in the ledger
  await agentNav.click();
  await el(page, "agent-pause", "button", /^pause$/i).click();
  await expect(page.getByTestId("agent-state")).toHaveText(/paused/i);
  connector(url);
  await agentNav.click();
  await el(page, "agent-ledger", "link", /see in ledger/i).click();
  await expect(page).toHaveURL(/\/ledger/);
  await expect(page.getByText(/paused/i).first()).toBeVisible();
  await expect(page.getByText(/refused/i).first()).toBeVisible();
  // the Agent filter narrows the list and the count follows it; All shows the steady order too
  const rows = page.getByTestId("ledger-entry");
  const mine = await rows.count();
  await expect(page.getByTestId("ledger-count")).toHaveText(`${mine} entries`);
  await page.locator("#ledger-all").click();
  await expect(page.getByTestId("ledger-group-S-1")).toBeVisible();
  const every = await rows.count();
  expect(every).toBeGreaterThan(mine);
  await expect(page.getByTestId("ledger-count")).toHaveText(`${every} entries`);

  // 8 Settings: the kitchen's name opens them; a diet change asks the code
  await page.getByTestId("nav-settings").or(page.getByTestId("phone-settings")).or(page.getByRole("link", { name: /hotel espoo kitchen/i })).filter({ visible: true }).first().click();
  await expect(page).toHaveURL(/\/settings/);
  await el(page, /^set-(nav|row)-diet$/, "link", /diet and allergens/i).click();
  const gluten = () => page.getByRole("switch", { name: /gluten/i }).or(page.getByRole("checkbox", { name: /gluten/i })).filter({ visible: true }).first();
  await expect(gluten()).not.toBeChecked();
  await gluten().click();
  await el(page, "diet-save", "button", /^save$/i).click();
  await typeCode(page);
  await expect(page.getByTestId("diet-saved")).toBeVisible();
  await page.reload();
  await expect(gluten()).toBeChecked();

  // B saw none of it
  await b.reload();
  await nav(b, "nav-inbox", /^inbox$/i).click();
  expect(await b.locator("main").innerText()).toBe(bInbox);
  await nav(b, "nav-agent", /^agent$/i).click();
  await expect(el(b, "agent-connect", "button", /^connect agent$/i)).toBeVisible();
  await other.close();
});
