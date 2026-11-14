import AxeBuilder from "@axe-core/playwright";
import { test, expect, type Page } from "@playwright/test";
import { CODE, demoLogin, slop } from "./helpers";

// The Agent page in fixture mode, every state: not connected, the pairing
// code, the consent card, connected, Technical open, Rules edited (wrong code,
// then saved), paused, the disconnect prompt, Rules never saved. Each state
// is checked with axe (WCAG 2.2 AA) and helpers.slop, and saved as a shot at
// 1280 and 390, light and dark: $SHOTS_AGENT/<state>-<width>-<theme>.png.
const OUT = process.env.SHOTS_AGENT ?? "../../artifacts/shots/agent";
const VIEWS = [
  { width: 1280, height: 900, theme: "light" },
  { width: 1280, height: 900, theme: "dark" },
  { width: 390, height: 844, theme: "light" },
  { width: 390, height: 844, theme: "dark" },
] as const;
const KEY = "validio-agent-mock-v1";

for (const v of VIEWS) {
  test(`agent page, every state, ${v.width} ${v.theme}`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: v.theme });
    await page.setViewportSize({ width: v.width, height: v.height });
    const problems: string[] = [];
    async function shoot(name: string) {
      await page.waitForTimeout(250);
      await page.screenshot({ path: `${OUT}/${name}-${v.width}-${v.theme}.png`, fullPage: true });
      problems.push(...(await slop(page)).map((x) => `${name}: ${x}`));
      const axe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();
      problems.push(...axe.violations.map((x) => `${name}: axe ${x.id} ${x.nodes.map((n) => n.target.join(" ")).join(", ")}`));
    }
    const open = async () => {
      await page.goto(`/agent?theme=${v.theme}`);
      await page.evaluate((t) => document.documentElement.setAttribute("data-theme", t), v.theme);
    };

    await page.goto("/login");
    await page.evaluate(() => localStorage.clear());
    await page.reload();
    await demoLogin(page);
    await open();
    // A fresh demo kitchen: rules saved, no agent yet.
    await expect(page.getByTestId("agent-state")).toHaveText("Not connected");
    await expect(page.getByTestId("rules-alone")).toContainText("1,200.00");
    await expect(page.getByTestId("rules-week")).toContainText("8,000.00");
    await shoot("none");

    await page.getByTestId("agent-connect").click();
    await expect(page.getByTestId("pair-code")).toHaveText(/^[A-Z2-9]{4}-[A-Z2-9]{4}$/);
    await shoot("pairing");
    await page.getByTestId("vendor-fold").click();
    await expect(page.getByTestId("mcp-url")).toContainText("/mcp/k/");
    await shoot("pairing-vendor");

    await page.getByTestId("agent-demo").click();
    await expect(page.getByTestId("consent")).toContainText("Order alone up to 1,200.00 €");
    await expect(page.getByTestId("pair-code")).toHaveCount(0);
    await shoot("consent");
    await page.getByTestId("consent-allow").click();
    await expect(page.getByTestId("agent-state")).toHaveText("Active");
    await expect(page.getByTestId("agent-used")).toHaveText("Not used yet");
    await expect(page.getByTestId("agent-ledger")).toHaveAttribute("href", "/ledger?pass=M-1");
    await shoot("active");

    await page.locator("#tech-fold summary").click();
    await expect(page.getByTestId("raw-pass")).toContainText('"id": "M-1"');
    await expect(page.locator("#tech-fold")).toContainText("Agent connected");
    await shoot("technical");
    await page.locator("#tech-fold summary").click();

    await page.getByTestId("rules-edit").click();
    await expect(page.getByTestId("r-alone")).toBeFocused();
    await page.getByTestId("r-alone").fill("900");
    await page.getByRole("radio", { name: "Extra cost" }).click();
    await expect(page.getByTestId("r-pct")).toBeVisible();
    await shoot("rules-edit");
    await page.getByTestId("code-input").fill("12");
    await page.getByTestId("code-submit").click();
    await expect(page.locator("#code-help")).toHaveText("Type the 6 digit code.");
    await shoot("rules-error");
    await page.getByTestId("code-input").fill(CODE);
    await page.getByTestId("code-submit").click();
    await expect(page.getByTestId("rules-alone")).toContainText("900.00");
    await expect(page.getByTestId("rules-subs")).toContainText(/Up to 5\s%\sextra/);
    await page.locator("#tech-fold summary").click();
    await expect(page.locator("#tech-fold")).toContainText("Rules changed");
    await page.locator("#tech-fold summary").click();

    await page.getByTestId("agent-pause").click();
    await expect(page.getByTestId("agent-state")).toHaveText("Paused");
    await expect(page.getByTestId("agent-pause")).toHaveText("Resume");
    await shoot("paused");

    await page.getByTestId("agent-disconnect").click();
    await expect(page.getByTestId("disconnect-confirm")).toBeVisible();
    await shoot("disconnect");
    await page.getByTestId("disconnect-confirm").click();
    await expect(page.getByTestId("agent-state")).toHaveText("Not connected");
    await expect(page.getByTestId("agent-demo")).toBeVisible();

    // A kitchen that never saved its Rules and has no agent yet.
    await page.evaluate((k) => {
      const m = JSON.parse(localStorage.getItem(k)!);
      m.agent = { state: "none", versions: [] };
      m.rules.saved = false;
      localStorage.setItem(k, JSON.stringify(m));
    }, KEY);
    await open();
    await expect(page.getByTestId("rules-unset")).toHaveText(/Needs approval/);
    await expect(page.getByTestId("rules-edit")).toHaveText("Set rules");
    await shoot("unset");

    expect(problems).toEqual([]);
  });
}

test("rules refuse alone above approval and a week below it", async ({ page }) => {
  await page.goto("/login");
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await demoLogin(page);
  await page.goto("/agent");
  await page.getByTestId("rules-edit").click();
  await page.getByTestId("r-alone").fill("6000");
  await page.getByTestId("code-input").fill(CODE);
  await page.getByTestId("code-submit").click();
  await expect(page.locator("#r-alone-problem")).toHaveText("Above needs approval.");
  await page.getByTestId("r-alone").fill("900");
  await page.getByTestId("r-week").fill("4000");
  await page.getByTestId("code-submit").click();
  await expect(page.locator("#r-week-problem")).toHaveText("Below needs approval.");
  await page.getByTestId("r-week").fill("");
  await page.getByTestId("code-submit").click();
  await expect(page.getByTestId("rules-week")).toContainText("No limit");
  await page.getByTestId("rules-edit").click();
  await page.getByRole("button", { name: "Cancel" }).click();
  await expect(page.getByTestId("rules-alone")).toContainText("900.00");
});
