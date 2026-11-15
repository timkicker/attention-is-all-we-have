# 001 — Lay the motion foundation: tokens, helpers, reduced motion, test config

- **Status**: DONE
- **Commit**: 61a5322
- **Severity**: HIGH (every other plan depends on it)
- **Category**: Cohesion & tokens, Accessibility
- **Estimated scope**: 5 files edited, 1 file created, ~150 lines

## Problem

The app has almost no motion and no motion vocabulary of its own. The only motion today:

```css
/* src/app.css:339-341 — current */
a.v-row,
a.vr {
  transition: background-color var(--duration-fast) ease;
}
/* src/app.css:698-704 — current */
details.fold > summary .chev {
  width: 14px;
  height: 14px;
  transition: transform var(--duration-fast) ease;
}
```

```css
/* src/routes/activity/[id]/Options.svelte:249-256 — current */
:global(.flash) {
  animation: flash var(--duration-slow) ease;
}
@keyframes flash {
  from {
    background: var(--valio-tint);
  }
}
```

The vendored Arlen kit (`vendor/arlen-ui-kit/src/lib/motion.css`, never edited) defines `--ease-out: cubic-bezier(0.2, 0.8, 0.2, 1)`, which is too weak for deliberate motion, and its reduced-motion block sets every `--duration-*` to `0ms !important`. That turns off all feedback rather than making it gentler.

Every later plan (002 to 017) needs one shared set of curves, durations and Svelte transitions. Without it, each plan would hand-type its own near-identical values.

## Target

1. New motion tokens in `src/lib/tokens.css`, the one file where design values live.
2. A reduced-motion block for those tokens. Movement goes to zero, and short opacity fades stay.
3. A new `src/lib/motion.ts` with an exact cubic-bezier solver, the same curves as JS easing functions, and three Svelte transitions (`rise`, `collapse`, `blurSwap`) that respect reduced motion.
4. Every Playwright config runs with `reducedMotion: "reduce"`. Tests then never race an animation, and axe never measures contrast mid-fade.
5. The motion rules live in `plans/README.md` ("Principles"). `UI-PLAN.md` is out of date and is **not** a constraint for these plans. Do not edit it.

## Repo conventions to follow

- Every colour, radius and design value lives in `src/lib/tokens.css`. `scripts/check-tokens.mjs` fails on colour and radius literals elsewhere. Curves are not checked, but keep them in tokens.css by convention.
- App tokens use the `--v-` prefix (e.g. `--v-line`, `--v-tint-hover`). Do not redefine the kit's own `--ease-*` / `--duration-*`.
- Svelte 5 runes only. Use `{@attach}` instead of `use:` actions. Before finishing any `.svelte` edit, run the `svelte-code-writer` skill (`npx @sveltejs/mcp@0.1.30` svelte-autofixer), per AGENTS.md.

## Steps

1. **`src/lib/tokens.css`**: inside the first block (`:root, :root[data-theme="light"] {`), directly after `--v-col: 1120px;`, add:

   ```css
   /* ---------- motion (plans/001) ----------
      Curves: ease-out for anything entering or leaving, ease-in-out for
      something moving on screen, the drawer curve for sheets. Never ease-in. */
   --v-ease-out: cubic-bezier(0.23, 1, 0.32, 1);
   --v-ease-in-out: cubic-bezier(0.77, 0, 0.175, 1);
   --v-ease-drawer: cubic-bezier(0.32, 0.72, 0, 1);
   --v-dur-press: 140ms; /* press feedback */
   --v-dur-ui: 200ms; /* folds, swaps, indicators */
   --v-dur-enter: 260ms; /* something arriving: a row, a view, a field */
   --v-dur-moment: 420ms; /* rare moments: approval done, set up, theme reveal */
   --v-dur-glow: 1200ms; /* the petrol tint a new or changed thing fades from */
   --v-rise: 6px; /* how far an entering thing travels */
   ```

   At the end of the file, after the existing `@media (max-width: 760px)` block, add:

   ```css
   /* Reduced motion: nothing travels, fades stay short. The kit already zeroes its own durations. */
   @media (prefers-reduced-motion: reduce) {
     :root,
     :root[data-theme] {
       --v-rise: 0px;
       --v-dur-press: 0ms;
       --v-dur-ui: 120ms;
       --v-dur-enter: 120ms;
       --v-dur-moment: 120ms;
       --v-dur-glow: 600ms;
     }
   }
   ```

2. **Create `src/lib/motion.ts`** with exactly this content:

   ```ts
   // The motion helpers every page shares (plans/001). Curves and durations mirror
   // the --v-ease-* and --v-dur-* tokens in tokens.css; change both together.
   import type { TransitionConfig } from "svelte/transition";

   /** An exact CSS cubic-bezier as an easing function (Newton-Raphson, then bisection). */
   export function bezier(x1: number, y1: number, x2: number, y2: number): (t: number) => number {
     const cx = 3 * x1, bx = 3 * (x2 - x1) - cx, ax = 1 - cx - bx;
     const cy = 3 * y1, by = 3 * (y2 - y1) - cy, ay = 1 - cy - by;
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
       let lo = 0, hi = 1;
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

   export const DUR = { press: 140, ui: 200, enter: 260, moment: 420, glow: 1200 } as const;

   export const reduced = (): boolean =>
     typeof matchMedia !== "undefined" && matchMedia("(prefers-reduced-motion: reduce)").matches;

   /** Fade in while travelling `y` px into place. Reduced motion: a 120 ms fade, no travel. */
   export function rise(_node: Element, { y = 6, duration = DUR.enter, delay = 0 } = {}): TransitionConfig {
     if (reduced()) return { duration: 120, delay: 0, css: (t) => `opacity: ${t}` };
     return { duration, delay, easing: easeOut, css: (t, u) => `opacity: ${t}; transform: translateY(${u * y}px)` };
   }

   /** Open or close the element's own height with a fade, for rows that arrive or leave a list.
    *  Animating height is the documented exception (accordions); keep it short. */
   export function collapse(node: HTMLElement, { duration = DUR.enter, delay = 0 } = {}): TransitionConfig {
     const h = node.offsetHeight;
     if (reduced()) return { duration: 120, css: (t) => `opacity: ${t}` };
     return {
       duration,
       delay,
       easing: easeOut,
       css: (t) => `overflow: hidden; height: ${t * h}px; opacity: ${t}`,
     };
   }

   /** A word or number swapping for another in place: fade with a 2 px blur so the two never double-expose. */
   export function blurSwap(_node: Element, { duration = DUR.ui, y = 0 } = {}): TransitionConfig {
     if (reduced()) return { duration: 120, css: (t) => `opacity: ${t}` };
     return {
       duration,
       easing: easeOut,
       css: (t, u) => `opacity: ${t}; filter: blur(${u * 2}px); transform: translateY(${u * y}px)`,
     };
   }
   ```

   (Formatting is up to the project's Prettier style. The values and logic are not.)

3. **`src/app.css`**: append at the end of the file:

   ```css
   /* ---------- motion shared by every page (plans/001) ---------- */
   /* The tint a new or changed thing fades from: a row the agent just added, a rule just saved. */
   .v-glow {
     animation: v-glow var(--v-dur-glow) var(--v-ease-out) 160ms backwards;
   }
   @keyframes v-glow {
     from {
       background-color: var(--valio-tint);
     }
   }
   /* Content that arrived after a skeleton: one entrance per container. */
   .v-arrive {
     animation: v-arrive var(--v-dur-enter) var(--v-ease-out) both;
   }
   @keyframes v-arrive {
     from {
       opacity: 0;
       transform: translateY(var(--v-rise));
     }
   }
   ```

   Then replace `Options.svelte:249-256` (the `.flash` rule and `@keyframes flash` quoted above) with nothing. Make `Options.svelte:74-75` add and remove `v-glow` instead of `flash`:

   ```ts
   row?.classList.add("v-glow");
   setTimeout(() => row?.classList.remove("v-glow"), 1600);
   ```

4. **Playwright configs**: in each of `playwright.config.ts`, `playwright.live.config.ts`, `playwright.accounts.config.ts`, `e2e-live/demo.config.ts` and `a11y/a11y.config.ts`, add `reducedMotion: "reduce"` to the top-level `use: { … }` object. Do NOT touch `scripts/record-video.mjs` or `scripts/shoot-accounts.mjs`: the demo video should show the motion.


## Boundaries

- Do NOT edit anything under `vendor/`.
- Do NOT change any existing token's value. Only add.
- Do NOT add dependencies.
- If a quoted excerpt does not match the file (drift since 61a5322), STOP and report.

## Verification

- **Mechanical**: `npm run check` passes (the token check and svelte-check). `npx playwright test` is green.
- **Feel check**: open an ordered request in Activity, open the supplier-text margin note, and click "Show this product". The row fades from the petrol tint over about 1.2 s. It does not blink.
- In DevTools Rendering, set `prefers-reduced-motion: reduce` and run `getComputedStyle(document.documentElement).getPropertyValue("--v-rise")` in the console. It returns `0px`.
- **Done when**: tokens, `motion.ts`, the app.css block and the 5 Playwright configs are in place, and the checks are green.
