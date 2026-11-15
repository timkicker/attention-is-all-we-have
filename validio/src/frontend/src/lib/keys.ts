// The app's few keys (plans/013), as a pure router: the layout passes the event and acts on the answer.
// Nothing here animates: keyboard actions are instant.
export type KeyAction =
  | { go: string }
  | { rows: 1 | -1 }
  | { palette: "open" | "keys" }
  | null;

const GO: Record<string, string> = { h: "/", a: "/activity", r: "/rules", n: "/agent", s: "/settings" };
const FILTER = ["/activity", "/activity?status=ordered", "/activity?status=waiting", "/activity?status=blocked", "/activity?status=standing"];

let prefixAt = 0;

/** True when the key belongs to whatever has focus: a field, an editor, a slider. */
export function typing(t: EventTarget | null): boolean {
  const el = t as HTMLElement | null;
  if (!el) return false;
  if (el.isContentEditable) return true;
  if (/^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName)) return true;
  return !!el.closest('[role="slider"], [role="combobox"], [role="listbox"], dialog[open]');
}

export function keyRouter(e: KeyboardEvent, ctx: { path: string }): KeyAction {
  if (e.metaKey || e.ctrlKey || e.altKey) return null;
  if (typing(e.target)) return null;
  const k = e.key;
  const now = Date.now();
  if (now - prefixAt < 1000) {
    prefixAt = 0;
    return GO[k] ? { go: GO[k] } : null;
  }
  if (k === "g") {
    prefixAt = now;
    return null;
  }
  if (k === "?") return { palette: "keys" };
  const onList = ctx.path === "/" || ctx.path === "/activity";
  if (onList && (k === "j" || k === "k")) return { rows: k === "j" ? 1 : -1 };
  if (ctx.path === "/activity" && /^[1-5]$/.test(k)) return { go: FILTER[Number(k) - 1] };
  return null;
}

/** Move focus to the next or previous activity row, without smooth scrolling. */
export function stepRows(dir: 1 | -1): void {
  const rows = [...document.querySelectorAll<HTMLElement>("a.ar")];
  if (!rows.length) return;
  const at = rows.indexOf(document.activeElement as HTMLElement);
  const next = rows[at === -1 ? (dir === 1 ? 0 : rows.length - 1) : Math.max(0, Math.min(rows.length - 1, at + dir))];
  next.focus({ preventScroll: true });
  next.scrollIntoView({ block: "nearest" });
}
