import { expect, type Page } from "@playwright/test";

/** Reset sits in the demo bar. */
export async function reset(page: Page) {
  await page.locator("#demo-reset").click();
}

/** From a clean state: the fixture's state and session live in localStorage. */
export async function fresh(page: Page) {
  await page.goto("/login");
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await demoLogin(page);
  await expect(page.locator("h1")).toHaveText("Home");
}

/** The login page's first button: a copy of the demo kitchen. */
export async function demoLogin(page: Page) {
  await page.getByTestId("try-demo").click();
  await expect(page).not.toHaveURL(/\/login/);
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
    // Proof entries ([data-raw]) are the hashed originals and stay as they were written.
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
      // The same reason on two rows of a table or a list is two rows.
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
