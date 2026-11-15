// The theme menu: Light is the default, System follows the device, Dark stays.
// A change from the Settings control or the palette reveals the new theme in a circle growing
// from where it was asked for (plans/016); the browser's status bar follows the band (plans/015).
export type Mode = "system" | "light" | "dark";
const KEY = "validio-theme";

function stored(): Mode {
  try {
    const v = localStorage.getItem(KEY);
    if (v === "system" || v === "dark") return v;
  } catch {
    // no storage: Light
  }
  return "light";
}

export const theme = $state({ mode: stored() as Mode });

/** The browser's own bar takes the band's colour, read from the tokens (no colour is written here). */
export function syncThemeColor(): void {
  const band = getComputedStyle(document.documentElement).getPropertyValue("--valio-band").trim();
  if (band) document.querySelector('meta[name="theme-color"]')?.setAttribute("content", band);
}

export function setMode(m: Mode, origin?: { x: number; y: number }) {
  theme.mode = m;
  try {
    if (m === "light") localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, m);
  } catch {
    // no storage: this visit only
  }
  const light = m === "system" ? matchMedia("(prefers-color-scheme: light)").matches : m === "light";
  const next = light ? "light" : "dark";
  const root = document.documentElement;
  const apply = () => {
    root.dataset.theme = next;
    syncThemeColor();
  };
  const doc = document as Document & { startViewTransition?: (cb: () => void) => { ready: Promise<void>; finished: Promise<void> } };
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (root.dataset.theme === next || !doc.startViewTransition || reduce) return apply();
  const x = origin?.x ?? innerWidth / 2;
  const y = origin?.y ?? innerHeight / 2;
  const r = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));
  root.dataset.vt = "theme";
  const t = doc.startViewTransition(apply);
  t.ready
    .then(() => {
      root.animate(
        { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${r}px at ${x}px ${y}px)`] },
        { duration: 1100, easing: "cubic-bezier(0.77, 0, 0.175, 1)", pseudoElement: "::view-transition-new(root)" },
      );
    })
    .catch(() => {});
  t.finished.finally(() => delete root.dataset.vt);
}
