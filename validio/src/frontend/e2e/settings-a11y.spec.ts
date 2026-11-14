import AxeBuilder from "@axe-core/playwright";
import { test, expect, type Page } from "@playwright/test";
import { demoLogin } from "./helpers";

// axe (WCAG 2.2 A and AA, contrast included) over Settings, the Inbox
// checklist and the example request, 1280 and 390, light and dark; on the
// phone every button and link there is at least 44 px high.
const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];
const VIEWS = [
  { width: 1280, height: 900, theme: "light" },
  { width: 1280, height: 900, theme: "dark" },
  { width: 390, height: 844, theme: "light" },
  { width: 390, height: 844, theme: "dark" },
] as const;

async function audit(page: Page, name: string, out: string[], phone: boolean) {
  await page.waitForTimeout(200);
  const r = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  for (const v of r.violations) out.push(`${name}: ${v.id} ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`);
  if (!phone) return;
  const small = await page.evaluate(() =>
    [...document.querySelectorAll<HTMLElement>("main button, main a, main [role=switch], main [role=radio]")]
      .filter((e) => e.offsetParent && e.getBoundingClientRect().height < 44 && !e.closest(".facts, .crumbs"))
      .map((e) => `${e.tagName.toLowerCase()} "${(e.textContent || e.getAttribute("aria-label") || "").trim().slice(0, 30)}"`),
  );
  for (const s of small) out.push(`${name}: under 44 px: ${s}`);
}

for (const v of VIEWS) {
  test(`settings a11y, ${v.width} ${v.theme}`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: v.theme });
    await page.setViewportSize({ width: v.width, height: v.height });
    const phone = v.width < 761;
    const out: string[] = [];
    const go = (path: string) => page.goto(`${path}?theme=${v.theme}`);
    await go("/login");
    await page.evaluate(() => localStorage.clear());
    await go("/login");
    await demoLogin(page);
    await go("/");
    await expect(page.getByTestId("example")).toBeVisible();
    await audit(page, "inbox", out, phone);
    if (phone) {
      await go("/settings");
      await expect(page.getByTestId("set-row-kitchen")).toBeVisible();
      await audit(page, "settings", out, phone);
    }
    for (const s of ["kitchen", "diet", "login", "theme"]) {
      await go(`/settings/${s}`);
      await expect(page.getByTestId(`settings-${s}`)).toBeVisible();
      await audit(page, s, out, phone);
    }
    await go("/settings/kitchen");
    await page.getByTestId("kitchen-edit").click();
    await audit(page, "kitchen edit", out, phone);
    await go("/settings/diet");
    await page.getByTestId("diet-VEGAN").click();
    await page.getByTestId("diet-save").click();
    await audit(page, "diet code", out, phone);
    expect(out, out.join("\n")).toEqual([]);
  });
}
