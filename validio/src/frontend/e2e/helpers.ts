import { expect, type Page } from "@playwright/test";

/** Reset sits in the demo bar. */
export async function reset(page: Page) {
  await page.locator("#demo-reset").click();
}

/**
 * The recorded stock-out: the kitchen's agent swapped the mozzarella and R-2
 * waits for the owner. No control in the app does this (an agent orders over
 * MCP); the test seeds the fixture's state the way that run left it.
 */
export async function stockOut(page: Page) {
  await page.goto("/");
  await page.evaluate(() => {
    const k = "validio-mock-v2";
    const s = JSON.parse(localStorage.getItem(k) ?? '{"moz":"none","steady":"pending"}');
    if (s.moz === "none") {
      // An accepted mozzarella line cannot stay accepted once the stock is gone.
      s.steady = s.steady === "mozzarella" ? "renewed" : s.steady === "both" ? "accepted" : s.steady;
      s.moz = "waiting";
    }
    localStorage.setItem(k, JSON.stringify(s));
  });
  await page.reload();
  await expect(page.locator("h1")).toHaveText("Inbox");
}

/** An MCP agent's first call (the fixture's window.validioMcpCall), its code checked, then Allow. */
export async function connectAgent(page: Page, path = "/agent") {
  await page.goto(path);
  await page.getByTestId("agent-connect").click();
  await expect(page.getByTestId("agent-state")).toHaveText("Waiting for your agent");
  const told = await page.evaluate(() => (window as unknown as { validioMcpCall: () => string | undefined }).validioMcpCall());
  expect(told).toMatch(/^[A-Z2-9]{3}-[A-Z2-9]{3}$/);
  await expect(page.getByTestId("verify-code")).toHaveText(told!, { timeout: 5000 });
  await page.getByTestId("consent-allow").click();
  await expect(page.getByTestId("agent-state")).toHaveText("Active");
}

/** From a clean state: the fixture's state and session live in localStorage. */
export async function fresh(page: Page) {
  await page.goto("/login");
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await demoLogin(page);
  await expect(page.locator("h1")).toHaveText("Inbox");
}

/** The login page's first button: a copy of the demo kitchen. */
export async function demoLogin(page: Page) {
  await page.getByTestId("try-demo").click();
  await expect(page).not.toHaveURL(/\/login/);
}

/** Type the approval code into the shared field, if the page asks for it. */
export async function code(page: Page) {
  await page.getByTestId("code-input").fill(CODE);
  await page.getByTestId("code-submit").click();
}

/** The fixture plays a server with the approval code set: any 6 digits. */
export const CODE = "246810";

/**
 * What a person reads on the page, checked for machine words: unit codes and
 * EUR, words in capitals, a product number standing alone as a heading, and
 * the same sentence twice outside a table. Returns the problems, empty when
 * the page is clean.
 */
export async function slop(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    // The ledger's "As recorded" text is the hashed original and stays as it was written.
    const raw = [...document.querySelectorAll<HTMLElement>("[data-raw]")];
    raw.forEach((e) => (e.style.display = "none"));
    const text = document.body.innerText;
    raw.forEach((e) => (e.style.display = ""));
    const out: string[] = [];
    for (const m of text.matchAll(/\b(\d[\d,.]*\s+)?(ST|BAG|EUR|KI|PCS|PSS|KPL)\b/g)) out.push(`unit code: "${m[0]}"`);
    for (const m of text.matchAll(/\b[A-ZÄÖÅ]{4,}\b/g)) out.push(`capitals: "${m[0]}"`);
    for (const h of document.querySelectorAll("h1, h2, h3")) {
      const t = (h as HTMLElement).innerText;
      if (/\b\d{6}\b/.test(t) && !/[a-z]{4,}/i.test(t.replace(/\b\d{6}\b/g, ""))) out.push(`number as title: "${t}"`);
    }
    const seen = new Map<string, number>();
    for (const el of document.querySelectorAll("p, li, h1, h2, h3, td, dd, span")) {
      const e = el as HTMLElement;
      if (e.children.length || !e.offsetParent) continue;
      // The same reason on two rows of a table or an option list is two rows; the inbox list and the
      // bar title repeat the open request as list entry and breadcrumb.
      if (e.closest("table, [role=table], .rc-ev, [aria-label=Requests], [data-raw], #bar-title")) continue;
      for (const s of e.innerText.split(/(?<=[.?!])\s+/)) {
        const k = s.trim().toLowerCase();
        if (k.split(" ").length < 6) continue;
        seen.set(k, (seen.get(k) ?? 0) + 1);
      }
    }
    for (const [k, n] of seen) if (n > 1) out.push(`twice: "${k}"`);
    return [...new Set(out)];
  });
}
