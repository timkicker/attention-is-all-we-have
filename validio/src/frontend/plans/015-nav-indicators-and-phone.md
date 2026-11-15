# 015 — Indicators that travel between tabs; the phone feels installed

- **Status**: DONE
- **Commit**: 61a5322
- **Severity**: LOW
- **Category**: Missed opportunities (spatial consistency), mobile polish
- **Depends on**: 001, 003 (view transitions for the nav and dock indicators)
- **Estimated scope**: 4 files, ~90 lines

## Problem

1. The selected marks teleport. The top nav underline (`.topnav a.on::after`), the phone dock bar (`.dock a.on::before`, both in `src/routes/+layout.svelte`), and the Activity filter underline (`border-bottom-color` on `.filters button[aria-pressed="true"]`, `src/app.css:500-505`) jump from one item to the next. These marks are the clearest "you moved from here to there" signal the app has.
2. On a phone the browser chrome does not match the app. `<meta name="theme-color" content="#0B4F66">` (`src/app.html:36`) is fixed, so in the dark theme the status bar stays light petrol over a near-black page. The filters row scrolls sideways with a visible scrollbar and no snapping.

## Target

| Indicator | How | Values |
|:---|:---|:---|
| Top nav underline | A real `<span class="nav-ink">` inside the active link, with `view-transition-name: v-nav-ink`. On navigation, plan 003's transition morphs it from the old link to the new one | `::view-transition-group(v-nav-ink) { animation-duration: 260ms; animation-timing-function: var(--v-ease-in-out); }` |
| Dock bar (phone) | the same, `v-dock-ink` | the same |
| Activity filter underline | One absolutely positioned bar under `.filters`, moved with `transform: translateX(px) scaleX(w)` measured from the pressed button. Same-path navigation has no view transition (plan 003), so this one is CSS | `transition: transform var(--v-dur-ui) var(--v-ease-in-out)`. No transition on first placement |

Plan 003 sets `animation: none` on the band and dock groups. The ink elements are their own named groups, so they still move while the frame stays still.

Filters are used tens of times a day, so this has to stay quick (200 ms) and plain: no stretch or squash.

**Phone polish** (mobile-native):
- `theme-color` follows the theme: on `setMode` and in the `app.html` boot script, set the meta to the computed `--valio-band` (light `#0b4f66`, dark `#003d50`, both read from tokens at runtime and never written as literals in `.ts`/`.svelte`).
- `.filters` on the phone: `scroll-snap-type: x proximity; scrollbar-width: none; overscroll-behavior-x: contain;`, buttons `scroll-snap-align: start`. Hide the WebKit scrollbar with `.filters::-webkit-scrollbar { display: none; }`.
- `-webkit-tap-highlight-color` and `touch-action` are already handled by plan 002.

## Repo conventions to follow

- Underlines are 2 px: `background: var(--valio-band-fg)` in the band, `var(--valio)` in the dock and filters.
- Keep the existing `aria-current="page"` and `aria-pressed`.

## Steps

1. `src/routes/+layout.svelte`:
   - In the topnav `{#each}`, inside the `<a>`, add `{#if p.match(path)}<span class="nav-ink" style:view-transition-name="v-nav-ink" aria-hidden="true"></span>{/if}`. Delete the `.topnav a.on::after` rule and keep `.kitchen.on::after` (Settings is outside the row). Style `.nav-ink { position: absolute; left: 0; right: 0; bottom: 0; height: 2px; background: var(--valio-band-fg); }`.
   - Dock: the same with `dock-ink` / `v-dock-ink` in place of `.dock a.on::before` (`top: -1px; left: 18%; right: 18%; height: 3px; background: var(--valio);`).
2. `src/app.css` (next to plan 003's block):
   ```css
   ::view-transition-group(v-nav-ink),
   ::view-transition-group(v-dock-ink) {
     animation-duration: 260ms;
     animation-timing-function: var(--v-ease-in-out);
   }
   ```
3. `src/routes/activity/+page.svelte`:
   - `bind:this` the `.filters` element. After each render where `status` changed, measure the pressed button's `offsetLeft` and `offsetWidth` and set `inkX` / `inkW` (`$state`). Do it in an `$effect` that reads `status` and `list.data` (the counts change widths).
   - `<span class="f-ink" class:ready style:transform="translateX({inkX}px) scaleX({inkW})" aria-hidden="true"></span>` inside `.filters`, with `.filters { position: relative; }` and `.f-ink { position: absolute; left: 0; bottom: 0; width: 1px; height: 2px; background: var(--valio); transform-origin: left; } .f-ink.ready { transition: transform var(--v-dur-ui) var(--v-ease-in-out); }`. Set `ready` one frame after the first placement (`requestAnimationFrame`) so the bar does not slide in from 0 on load.
   - In `src/app.css` remove `border-bottom-color: var(--valio);` from `.filters button[aria-pressed="true"]`, **only** for `.filters` (keep it for `.tabs [role="tab"][aria-selected="true"]`). Split the shared selector.
   - On the phone `.filters` scrolls, so `offsetLeft` is relative to the scroll content, and the ink scrolls with it as a child. Good.
4. Theme colour: in `src/lib/theme.svelte.ts` `setMode`, after setting `data-theme`, run `document.querySelector('meta[name="theme-color"]')?.setAttribute("content", getComputedStyle(document.documentElement).getPropertyValue("--valio-band").trim())`. Do the same at the end of the `app.html` boot script's `set()`, wrapped in `requestAnimationFrame`, because tokens load after the inline script.
5. Filters phone CSS in `src/routes/activity/+page.svelte`'s `@media (max-width: 760px)` block.

## Boundaries

- Do NOT animate nav or dock link colours beyond the existing 150 ms colour transition.
- Do NOT make the indicator stretch or bounce.
- If an excerpt does not match, STOP and report.

## Verification

- **Mechanical**: `npm run check`. `npx playwright test e2e/shell.spec.ts e2e/activity.spec.ts`. `make a11y`.
- **Feel check**:
  - Desk: Home, then Rules. The white underline glides across the band in about a quarter second, and the band itself does not flicker.
  - Activity: click Waiting, then Standing, then All. The petrol bar slides and resizes to each word. Reload on `?status=blocked`: the bar is already under Blocked, with no slide-in.
  - Phone (real device, dark theme): the status bar is the dark band colour. Filters snap to a word when flicked, with no scrollbar.
  - Reduced motion: the view-transition indicators do not animate (plan 003 skips transitions), and the filter bar jumps. Add `@media (prefers-reduced-motion: reduce) { .f-ink.ready { transition: none; } }` in step 3 for that.
- **Done when**: every "selected" mark travels to its new place, and the phone's chrome matches the theme.
