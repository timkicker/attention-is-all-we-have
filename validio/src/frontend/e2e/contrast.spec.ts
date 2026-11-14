import { test, expect, type Page } from "@playwright/test";
import { fresh } from "./helpers";

// Text on every control holds its contrast at rest, under the pointer, with
// keyboard focus and while pressed, in both themes. axe only reads the page at
// rest, so a hover that paints the label in the colour of its own fill (the
// pressed Activity chip, 14 Nov: white on near-white, only the count left)
// passed every audit. Colours are read from computed styles, not pixels:
// each layer's background is composited from the root down and the text's
// colour (times every ancestor's opacity) over that. 4.5:1 for text, 3:1 for
// large text and icons (WCAG 1.4.3, 1.4.11). Transitions are switched off so
// the reading is the end state, not a frame halfway.

const ROUTES = ["/", "/activity", "/activity?status=waiting", "/activity/R-4", "/rules", "/settings", "/agent"];
const CONTROLS = "a[href], button, summary, [role=tab], [role=button], [role=radio], [role=link]";
const STATES = ["rest", "hover", "focus", "active"] as const;

// Runs in the page: what each piece of text (and each icon) inside the control marked
// data-contrast="<i>" reads against what is painted behind it.
function measure(i: string) {
  const cv = document.createElement("canvas");
  cv.width = cv.height = 1;
  const cx = cv.getContext("2d", { willReadFrequently: true })!;
  // the canvas resolves any CSS colour syntax (color-mix, oklch, color(srgb ...)) to sRGB bytes
  const rgba = (s: string): number[] => {
    cx.clearRect(0, 0, 1, 1);
    cx.fillStyle = "#000";
    cx.fillStyle = s;
    cx.fillRect(0, 0, 1, 1);
    const d = cx.getImageData(0, 0, 1, 1).data;
    return [d[0], d[1], d[2], d[3] / 255];
  };
  const over = (top: number[], bot: number[]) => [0, 1, 2].map((k) => top[k] * top[3] + bot[k] * (1 - top[3])).concat(1);
  const lum = (c: number[]) => {
    const f = (v: number) => ((v /= 255) <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]);
  };
  const ratio = (a: number[], b: number[]) => {
    const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p);
    return (x + 0.05) / (y + 0.05);
  };
  const behind = (el: Element) => {
    const chain: Element[] = [];
    for (let e: Element | null = el; e; e = e.parentElement) chain.unshift(e);
    return chain.reduce((c, e) => over(rgba(getComputedStyle(e).backgroundColor), c), [255, 255, 255, 1]);
  };
  const el = document.querySelector(`[data-contrast="${i}"]`)!;
  const parts = new Set<Element>();
  const walk = (n: Node) => {
    for (const c of Array.from(n.childNodes)) {
      if (c.nodeType === Node.TEXT_NODE && c.textContent?.trim()) parts.add(c.parentElement!);
      else if (c.nodeType === Node.ELEMENT_NODE && (c as Element).tagName.toLowerCase() !== "svg") walk(c);
    }
  };
  walk(el);
  el.querySelectorAll("svg").forEach((s) => parts.add(s));
  const out: { what: string; ratio: number; need: number }[] = [];
  for (const t of parts) {
    const s = getComputedStyle(t);
    if (s.visibility === "hidden" || !t.getClientRects().length) continue;
    let opacity = 1;
    for (let e: Element | null = t; e; e = e.parentElement) opacity *= Number(getComputedStyle(e).opacity);
    const bg = behind(t);
    const fg = rgba(s.color);
    fg[3] *= opacity;
    const icon = t.tagName.toLowerCase() === "svg";
    const size = parseFloat(s.fontSize);
    const large = size >= 24 || (size >= 18.66 && Number(s.fontWeight) >= 700);
    out.push({
      what: icon ? "[icon]" : (t.textContent ?? "").trim().slice(0, 30),
      ratio: Math.round(ratio(over(fg, bg), bg) * 100) / 100,
      need: icon || large ? 3 : 4.5,
    });
  }
  return out;
}

async function sweep(page: Page, route: string): Promise<string[]> {
  await page.goto(route);
  await page.waitForLoadState("networkidle");
  await page.addStyleTag({ content: "*, *::before, *::after { transition: none !important; animation: none !important; }" });
  const n = await page.evaluate((sel) => {
    let i = 0;
    for (const e of Array.from(document.querySelectorAll(sel))) {
      const r = e.getBoundingClientRect();
      if (r.width && r.height && getComputedStyle(e).visibility !== "hidden" && !e.matches(":disabled")) e.setAttribute("data-contrast", String(i++));
    }
    return i;
  }, CONTROLS);
  const low: string[] = [];
  for (let i = 0; i < n; i++) {
    const el = page.locator(`[data-contrast="${i}"]`);
    const name = await el.evaluate((e) => `${e.tagName.toLowerCase()}${e.id ? `#${e.id}` : ""} "${(e.textContent ?? "").trim().replace(/\s+/g, " ").slice(0, 30)}"`);
    for (const state of STATES) {
      await page.mouse.move(0, 0);
      await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
      // A control another layer covers (the phone dock, a sticky bar) cannot be hovered: nothing to read.
      try {
        if (state === "hover" || state === "active") await el.hover({ timeout: 1000 });
        if (state === "focus") await el.focus({ timeout: 1000 });
      } catch {
        continue;
      }
      if (state === "active") await page.mouse.down();
      const parts = await page.evaluate(measure, String(i));
      // released away from the control, so the press never clicks
      if (state === "active") {
        await page.mouse.move(0, 0);
        await page.mouse.up();
      }
      for (const p of parts) if (p.ratio < p.need) low.push(`${route} ${state} ${name}: "${p.what}" ${p.ratio}:1, needs ${p.need}:1`);
    }
  }
  return low;
}

for (const scheme of ["dark", "light"] as const) {
  test(`every control keeps its text readable at rest, hovered, focused and pressed (${scheme})`, async ({ page }) => {
    test.setTimeout(240_000);
    await page.emulateMedia({ colorScheme: scheme });
    await fresh(page);
    const low: string[] = [];
    for (const r of ROUTES) low.push(...(await sweep(page, r)));
    expect(low).toEqual([]);
  });
}

test("the pressed filter chip keeps its label under the pointer on the phone, both themes", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await fresh(page);
  for (const scheme of ["dark", "light"] as const) {
    await page.emulateMedia({ colorScheme: scheme });
    expect(await sweep(page, "/activity?status=waiting")).toEqual([]);
  }
});
