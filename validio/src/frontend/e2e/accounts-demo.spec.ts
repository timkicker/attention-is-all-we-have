import { test, expect, type Page, type Locator } from "@playwright/test";
import { CODE } from "./helpers";

// "Done means" of the accounts plan, clicked in a fresh browser: try the demo kitchen, connect the demo
// agent, send the example request and see it ordered, lower the alone limit in Rules with the code, send
// again and see it wait, approve with the code, pause the agent and see the refusal in the ledger, change
// the diet in Settings. A second browser holds its own demo copy and must not see any of it.
//
// Against the built web app of the default config, or against a running server or the public link:
//   ACCOUNTS_BASE=http://127.0.0.1:8410 npx playwright test e2e/accounts-demo.spec.ts
// Skips itself while the Agent page is not in the sidebar.
//
// Numbers: the demo template (alone up to 1,200.00 €, the example 1,010.00 €), lowered to 800 €.
const BASE = process.env.ACCOUNTS_BASE;
if (BASE) test.use({ baseURL: BASE });

/** A control by its test id, or else by its role and visible label (the labels in docs/DEMO.md). */
function el(page: Page, id: string, role: "button" | "link" | "tab" | "checkbox" | "textbox", name: RegExp): Locator {
  return page.getByTestId(id).or(page.getByRole(role, { name })).first();
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

async function typeCode(page: Page) {
  const box = page.getByTestId("code-input").or(page.getByLabel(/approval code/i)).first();
  await expect(box).toBeVisible();
  await box.fill(CODE);
  await page.getByTestId("code-submit").or(page.getByRole("button", { name: /^(confirm|save|approve|ok)$/i })).first().click();
}

async function sendExample(page: Page) {
  await nav(page, "nav-inbox", /^inbox$/i).click();
  await el(page, "send-example", "button", /send example request/i).click();
}

test("the demo path, end to end, in a fresh browser", async ({ page, browser }) => {
  test.setTimeout(180_000);
  await freshDemo(page);
  const agentNav = nav(page, "nav-agent", /^agent$/i);
  test.skip((await agentNav.count()) === 0, "the Agent page is not in the sidebar yet");

  // the demo bar names the code on purpose
  await expect(page.getByText(CODE).first()).toBeVisible();

  // a second browser with its own copy, opened before A acts
  const other = await browser.newContext({ baseURL: BASE ?? test.info().project.use.baseURL });
  const b = await other.newPage();
  await freshDemo(b);
  await nav(b, "nav-inbox", /^inbox$/i).click();
  const bInbox = await b.locator("main").innerText();

  // 2 connect the demo agent
  await agentNav.click();
  await el(page, "agent-connect", "button", /^connect agent$/i).click();
  await expect(page.getByTestId("pairing-code").or(page.getByText(/^[A-Z0-9]{4}-[A-Z0-9]{4}$/)).first()).toBeVisible();
  await el(page, "agent-demo", "button", /connect the demo agent/i).click();
  await expect(page.getByText(/order alone up to 1,200\.00 €/i).first()).toBeVisible();
  await el(page, "agent-allow", "button", /^allow$/i).click();
  await expect(page.getByText(/^active$/i).first()).toBeVisible();

  // 3 the example request, ordered alone
  await sendExample(page);
  await expect(page.getByText(/ordered alone/i).first()).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("1,010.00 €").first()).toBeVisible();

  // 4 lower the alone limit in Rules, with the code
  await agentNav.click();
  await el(page, "agent-rules", "link", /^rules$/i).or(page.getByRole("button", { name: /^rules$/i })).first().click();
  const alone = page.getByTestId("rules-alone").or(page.getByLabel(/orders? alone up to/i)).first();
  await alone.fill("800");
  await el(page, "rules-save", "button", /^save$/i).click();
  await typeCode(page);
  await expect(alone).toHaveValue(/^800([.,]00)?$/);

  // 5 the same request again waits
  await sendExample(page);
  const waiting = page.getByText(/waiting for you/i).first();
  await expect(waiting).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/blocked/i)).toHaveCount(0);

  // 6 approve with the code
  await waiting.click();
  await el(page, "open-approval", "link", /open approval/i).or(page.getByRole("button", { name: /open approval/i })).first().click();
  await typeCode(page);
  await expect(page.getByText(/^(placed|ordered|approved)\b/i).first()).toBeVisible({ timeout: 30_000 });

  // 7 pause, send again, the refusal stands in the ledger
  await agentNav.click();
  await el(page, "agent-pause", "button", /^pause$/i).click();
  await expect(page.getByText(/^paused$/i).first()).toBeVisible();
  await sendExample(page);
  await expect(page.getByText(/paused this agent/i).first()).toBeVisible({ timeout: 30_000 });
  await agentNav.click();
  await el(page, "agent-ledger", "link", /see in ledger/i).click();
  await expect(page).toHaveURL(/\/ledger/);
  await expect(page.getByText(/paused/i).first()).toBeVisible();
  await expect(page.getByText(/refused/i).first()).toBeVisible();

  // 8 Settings: the kitchen's name opens them; a diet change asks the code
  await page.getByTestId("kitchen-settings").or(page.getByRole("link", { name: /hotel espoo kitchen/i })).first().click();
  await expect(page).toHaveURL(/\/settings/);
  await page.getByTestId("diet-FREE_FROM_GLUTEN").or(page.getByRole("checkbox", { name: /gluten/i })).first().check();
  await el(page, "diet-save", "button", /^save$/i).click();
  await typeCode(page);
  await page.reload();
  await expect(page.getByTestId("diet-FREE_FROM_GLUTEN").or(page.getByRole("checkbox", { name: /gluten/i })).first()).toBeChecked();

  // B saw none of it
  await b.reload();
  await nav(b, "nav-inbox", /^inbox$/i).click();
  expect(await b.locator("main").innerText()).toBe(bInbox);
  await nav(b, "nav-agent", /^agent$/i).click();
  await expect(el(b, "agent-connect", "button", /^connect agent$/i)).toBeVisible();
  await other.close();
});
