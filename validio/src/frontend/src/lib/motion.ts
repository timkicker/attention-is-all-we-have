// The motion helpers every page shares (plans/001). Curves and durations mirror
// the --v-ease-* and --v-dur-* tokens in tokens.css; change both together.
import type { TransitionConfig } from "svelte/transition";

/** An exact CSS cubic-bezier as an easing function (Newton-Raphson, then bisection). */
export function bezier(x1: number, y1: number, x2: number, y2: number): (t: number) => number {
  const cx = 3 * x1;
  const bx = 3 * (x2 - x1) - cx;
  const ax = 1 - cx - bx;
  const cy = 3 * y1;
  const by = 3 * (y2 - y1) - cy;
  const ay = 1 - cy - by;
  const sx = (t: number) => ((ax * t + bx) * t + cx) * t;
  const sy = (t: number) => ((ay * t + by) * t + cy) * t;
  const dx = (t: number) => (3 * ax * t + 2 * bx) * t + cx;
  const solve = (x: number) => {
    let t = x;
    for (let i = 0; i < 8; i++) {
      const e = sx(t) - x;
      if (Math.abs(e) < 1e-6) return t;
      const d = dx(t);
      if (Math.abs(d) < 1e-6) break;
      t -= e / d;
    }
    let lo = 0;
    let hi = 1;
    t = x;
    while (hi - lo > 1e-6) {
      const v = sx(t);
      if (Math.abs(v - x) < 1e-6) return t;
      if (x > v) lo = t;
      else hi = t;
      t = (lo + hi) / 2;
    }
    return t;
  };
  return (x) => (x <= 0 ? 0 : x >= 1 ? 1 : sy(solve(x)));
}

export const easeOut = bezier(0.23, 1, 0.32, 1);
export const easeInOut = bezier(0.77, 0, 0.175, 1);
export const easeDrawer = bezier(0.32, 0.72, 0, 1);
/** CSS `ease`, for the toast (Sonner's curve). */
export const ease = bezier(0.25, 0.1, 0.25, 1);

export const DUR = {
  press: 140,
  ui: 200,
  enter: 260,
  moment: 420,
  glow: 1200,
  tab: 620,
  wave: 800,
  theme: 1100,
  spark: 900,
  listen: 3000,
  chain: 140,
} as const;

/** The curves as CSS strings, for the Web Animations API (the same as the tokens). */
export const CSS_EASE = {
  out: "cubic-bezier(0.23, 1, 0.32, 1)",
  inOut: "cubic-bezier(0.77, 0, 0.175, 1)",
  drawer: "cubic-bezier(0.32, 0.72, 0, 1)",
} as const;

/** True while the tab is hidden: loops pause, nothing runs off screen. */
export const hidden = (): boolean => typeof document !== "undefined" && document.visibilityState === "hidden";

export const reduced = (): boolean =>
  typeof matchMedia !== "undefined" && matchMedia("(prefers-reduced-motion: reduce)").matches;

const fade = (duration = 120): TransitionConfig => ({ duration, css: (t) => `opacity: ${t}` });

/** Fade in while travelling `y` px into place. Reduced motion: a 120 ms fade, no travel. */
export function rise(_node: Element, { y = 6, duration: d = DUR.enter, delay = 0 }: { y?: number; duration?: number; delay?: number } = {}): TransitionConfig {
  if (reduced()) return fade();
  return { duration: d, delay, easing: easeOut, css: (t, u) => `opacity: ${t}; transform: translateY(${u * y}px)` };
}

/** Open or close the element's own height with a fade, for rows that arrive or leave a list.
 *  Animating height is the documented exception (accordions); keep it short. */
export function collapse(node: Element, { duration: d = DUR.enter, delay = 0 }: { duration?: number; delay?: number } = {}): TransitionConfig {
  const h = (node as HTMLElement).offsetHeight;
  if (reduced()) return fade();
  return { duration: d, delay, easing: easeOut, css: (t) => `overflow: hidden; height: ${t * h}px; opacity: ${t}` };
}

/** A word or number swapping for another in place: fade with a 2 px blur so the two never double-expose. */
export function blurSwap(_node: Element, { duration: d = DUR.ui, y = 0 }: { duration?: number; y?: number } = {}): TransitionConfig {
  if (reduced()) return fade();
  return { duration: d, easing: easeOut, css: (t, u) => `opacity: ${t}; filter: blur(${u * 2}px); transform: translateY(${u * y}px)` };
}

/** A plain fade, for exits. */
export function fadeOut(_node: Element, { duration: d = 140 }: { duration?: number } = {}): TransitionConfig {
  return { duration: reduced() ? 120 : d, easing: easeOut, css: (t) => `opacity: ${t}` };
}

/** Run `fn` inside a view transition when the browser has them and motion is allowed. */
export async function viewTransition(fn: () => Promise<void> | void): Promise<void> {
  const doc = document as Document & { startViewTransition?: (cb: () => Promise<void> | void) => { finished: Promise<void> } };
  if (!doc.startViewTransition || reduced()) return void (await fn());
  await doc.startViewTransition(fn).finished;
}

const sleepFor = (ms: number) => new Promise((r) => setTimeout(r, ms));
export { sleepFor as sleep };

/** One short tap on a phone that has it, for a decision that landed. Never under reduced motion. */
export function buzz(): void {
  if (reduced()) return;
  (navigator as Navigator & { vibrate?: (ms: number) => boolean }).vibrate?.(10);
}
