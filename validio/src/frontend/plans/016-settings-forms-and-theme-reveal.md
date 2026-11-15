# 016 — Settings: forms that open under their row, saves that confirm, a theme switch that reveals itself

- **Status**: DONE
- **Commit**: 61a5322
- **Severity**: LOW
- **Category**: Missed opportunities (state indication, feedback, delight at a rare action)
- **Depends on**: 001, 003 (shares the View Transitions setup)
- **Estimated scope**: 5 files, ~110 lines

## Problem

1. **Edit forms teleport.** In Settings, "Change" on a row (`src/routes/settings/EditRow.svelte`) passes `below={open ? children : undefined}` to the kit `Row`. The form appears and disappears in one frame, and everything below jumps.
2. **Saves are silent.** After Save, the form closes and the row's value changes text. Nothing says it worked (the Approval code section sets a `done` flag; Kitchen and Login only close).
3. **The theme switch** (`src/routes/settings/Theme.svelte`, kit `SegmentedControl` calling `setMode`) flips every colour on the page in one frame. That is a hard flash, especially from light to dark on a projector. Changing theme is rare: the right tier for one well-made moment.

## Target

| Moment | Motion | Values |
|:---|:---|:---|
| A row's form opens | `in:collapse` on the form's root | 260 ms `--v-ease-out` (height + opacity) |
| A row's form closes (Cancel or after Save) | `out:collapse={{ duration: 160 }}` | exits are shorter |
| Saved | The row's value gets `.v-glow` (petrol tint fading over 1200 ms). An inline "Saved" with a lucide `Check` (14 px, `--v-ok-text`) fades in beside the value through `in:blurSwap`, stays 2 s, then leaves with `out:` fade 200 ms. `role="status"` announces it | — |
| Theme change from the Settings control | View Transition with a circular reveal of the new theme from the centre of the clicked segment: `clip-path: circle(0 at x y)` to `circle(r at x y)` on `::view-transition-new(root)`, where r is the distance to the farthest viewport corner | **420 ms `cubic-bezier(0.77, 0, 0.175, 1)`** (`--v-ease-in-out`, a full-screen move across the screen), through WAAPI with `pseudoElement: "::view-transition-new(root)"` |
| Theme change from the OS ("System" following the device) or from the palette (plan 013) | no reveal from the OS. From the palette, the reveal starts at the viewport centre | — |

During the theme transition, the named groups from plan 003 (band, dock, page) must not run their own animations, or the reveal shows sliding pieces. Mark the root with `data-vt="theme"` for the duration and turn those animations off under it.

Reduced motion: no reveal. The theme switches instantly (that is a colour change, not motion).

## Repo conventions to follow

- `setMode(m)` in `src/lib/theme.svelte.ts` is the one place the theme changes. Keep it the only place.
- Settings sections: `Kitchen.svelte`, `Login.svelte`, `Code.svelte` use `EditRow` + `Form`.
- Keep the testids (`{id}-value`, `{id}-change`, the form ids). `e2e/settings.spec.ts` covers them.

## Steps

1. `src/routes/settings/Form.svelte`: give the root element `in:collapse out:collapse={{ duration: 160 }}` (import from `$lib/motion`). The root sits inside the kit Row's `{#if below}` block, so these local transitions play exactly on open and close. If the root is not a plain element, wrap it in `<div>`.
2. `src/routes/settings/EditRow.svelte`: add a prop `saved?: boolean`. When true, add `class="v-glow"` on `.er-value` and render `{#if saved}<span class="er-saved" role="status" in:blurSwap out:fade={{ duration: 200 }}><Check size={14} aria-hidden="true" />Saved</span>{/if}`. Each section (`Kitchen`, `Login`, `Code`) sets its `saved` state true after a successful save and false after 2000 ms (`setTimeout`, cleared on unmount).
3. `src/lib/theme.svelte.ts`: change the signature to `setMode(m: Mode, origin?: { x: number; y: number })`. Move the `data-theme` write into `const apply = () => {…}`. Then:

   ```ts
   const canReveal = typeof document !== "undefined" && "startViewTransition" in document && !matchMedia("(prefers-reduced-motion: reduce)").matches;
   if (!canReveal) return apply();
   const x = origin?.x ?? innerWidth / 2, y = origin?.y ?? innerHeight / 2;
   const r = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));
   document.documentElement.dataset.vt = "theme";
   const t = document.startViewTransition(apply);
   t.ready.then(() => {
     document.documentElement.animate(
       { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${r}px at ${x}px ${y}px)`] },
       { duration: 420, easing: "cubic-bezier(0.77, 0, 0.175, 1)", pseudoElement: "::view-transition-new(root)" },
     );
   });
   t.finished.finally(() => delete document.documentElement.dataset.vt);
   ```
4. `src/app.css`, next to plan 003's block:

   ```css
   :root[data-vt="theme"]::view-transition-old(root),
   :root[data-vt="theme"]::view-transition-new(root) {
     animation: none;
     mix-blend-mode: normal;
   }
   :root[data-vt="theme"]::view-transition-group(*),
   :root[data-vt="theme"]::view-transition-old(*),
   :root[data-vt="theme"]::view-transition-new(*) {
     animation: none;
   }
   ```

   The first rule must come after the second (or carry higher specificity). Check that the WAAPI clip animation still applies, because it is a script animation on the pseudo, not a CSS one. If `animation: none` on `*` interferes, scope the second rule to the named groups `v-band`, `v-dock`, `v-page`, `v-demo`, `v-nav-ink`, `v-dock-ink`.
5. `src/routes/settings/Theme.svelte`: the kit `SegmentedControl`'s `onchange` gives only the value. Compute the origin from the selected segment: `const el = document.querySelector('#theme [aria-checked="true"], #theme [data-state="on"]')` after `tick()`. Inspect the kit's segmented-control markup for the right selector and use the element's bounding-rect centre. Call `setMode(v as Mode, origin)`.

## Boundaries

- Do NOT animate colour changes on individual elements during the theme switch. The reveal does the whole page at once.
- Do NOT reveal on OS-driven changes.
- If an excerpt does not match, STOP and report.

## Verification

- **Mechanical**: `npm run check`, `npx playwright test e2e/settings.spec.ts e2e/contrast.spec.ts` (contrast disables animations itself), `make a11y`.
- **Feel check**:
  - Settings, Kitchen, Change: the form slides open under the row, and Cancel folds it faster. Save: the value tints and "Saved" appears and leaves after 2 s.
  - Theme: Dark. A dark circle grows from the "Dark" segment until it fills the screen in under half a second, with no flash and nothing sliding. Back to Light: the same from the "Light" segment. At 10% playback, the edge is clean and the band does not move.
  - Safari 17 / Firefox: the theme switches instantly, with no errors.
  - Reduced motion: an instant switch. Forms fade.
- **Done when**: no Settings change is silent or jumps, and the theme switch is one clean reveal.
