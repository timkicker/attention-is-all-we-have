# 002 — Give every pressable thing press feedback, gate hover to real pointers

- **Status**: DONE
- **Commit**: 61a5322
- **Severity**: HIGH
- **Category**: Physicality & origin, Accessibility
- **Depends on**: 001 (tokens `--v-ease-out`, `--v-dur-press`, `--v-dur-ui`)
- **Estimated scope**: 4 files, ~80 lines of CSS

## Problem

The kit `Button` already presses (`active:scale-[0.97]` in `vendor/.../button/button.svelte:9`). The app's own clickable elements do not. A tap on any of these gives no sign that it registered until the next page paints:

- the activity row `a.ar` (`src/lib/v2/ActivityRow.svelte:35-53`), clicked tens of times a day
- the filters `.filters button` (`src/app.css:478-505`)
- the phone dock tabs `.dock a` (`src/routes/+layout.svelte`, style block `/* ---------- the phone ---------- */`)
- `a.vr` / `a.v-row` link rows (`src/app.css:339-345`), the rule row `.rule-row` (`src/routes/activity/[id]/+page.svelte:~452-470`), the Home figure link `a.fig` (`src/routes/+page.svelte`, `.fig.end`)
- text buttons: `.db-reset` (layout), `.link-btn` (login), `details.fold > summary` (`src/app.css:680-705`)

Hover styles fire on touch screens as a "sticky hover" after a tap, for example:

```css
/* src/lib/v2/ActivityRow.svelte:52-57 — current */
.ar:hover {
  background: var(--v-tint-hover);
}
.ar:hover .ar-title {
  color: var(--valio);
}
```

Mobile Safari and Chrome also draw their grey tap flash over all of these.

## Target

Each element is tens per day (rows, filters, tabs), so the feedback has to be near-imperceptible and instant:

| Element | Press (`:active`) | Why this and not scale |
|:---|:---|:---|
| Full-width rows (`a.ar`, `a.vr`, `a.v-row`, `.rule-row`, `a.fig`) | `background-color: var(--v-tint-fill)`, `transition-duration: 0ms` while pressed | Scaling a full-width row shifts its hairlines. A darker wash reads as a press |
| `.filters button`, `.db-reset`, `.link-btn`, `details.fold > summary` | `transform: scale(0.97)` | Small targets: the kit button's own press |
| Dock tab icon (`.dock :global(.dock-icon)`) | `transform: scale(0.95)` on the icon only | The label stays still and readable |

Shared values: `transition: transform var(--v-dur-press) var(--v-ease-out)` for scaling, and `background-color var(--duration-fast) ease` for washes. Under reduced motion `--v-dur-press` is `0ms` (from plan 001), so the press snaps without travelling.

All `:hover` rules in the files below move inside `@media (hover: hover) and (pointer: fine) { … }`.

Global touch polish in `src/app.css`, inside the existing cursor rule's selector list:

```css
-webkit-tap-highlight-color: transparent;
touch-action: manipulation;
```

## Repo conventions to follow

- Washes come from tokens only: `--v-tint-hover` (hover) and `--v-tint-fill` (press) already exist in `tokens.css`.
- Exemplar of an existing hover-colour transition to keep: `src/app.css:354` `transition: color var(--duration-fast) ease;`.
- Run the `svelte-code-writer` autofixer on every edited `.svelte` file.

## Steps

1. **`src/app.css`**:
   - In the rule that sets `cursor: pointer` on `a[href], button, summary, …` (starts at about line 66), add `-webkit-tap-highlight-color: transparent;` and `touch-action: manipulation;`.
   - Wrap `a.v-row:hover .v-row-title, a.vr:hover .vr-value { color: var(--valio); }` (lines 343-345) in `@media (hover: hover) and (pointer: fine)`.
   - After line 341, add:
     ```css
     a.v-row:active,
     a.vr:active {
       background-color: var(--v-tint-fill);
       transition-duration: 0ms;
     }
     ```
   - `.filters button` (line 479): add `transition: color var(--duration-fast) ease, transform var(--v-dur-press) var(--v-ease-out);`, plus a rule `.filters button:active { transform: scale(0.97); }`. Wrap `.tabs [role="tab"]:hover, .filters button:hover` (lines 496-499) in the hover media query.
   - `details.fold > summary` (line 680): add `transition: transform var(--v-dur-press) var(--v-ease-out);` and `details.fold > summary:active { transform: scale(0.97); }`. Set `transform-origin: left center` so it presses toward its chevron. Wrap `details.fold > summary:hover` (line 694) in the hover media query.
2. **`src/lib/v2/ActivityRow.svelte`**: put `.ar:hover` and `.ar:hover .ar-title` (lines 52-57) inside `@media (hover: hover) and (pointer: fine)`. Add:
   ```css
   .ar:active {
     background: var(--v-tint-fill);
     transition-duration: 0ms;
   }
   ```
3. **`src/routes/+layout.svelte`** (style block):
   - Wrap `.topnav a:hover, .kitchen:hover` and `.db-reset:hover` in the hover media query.
   - `.db-reset`: add `transition: transform var(--v-dur-press) var(--v-ease-out);` and `.db-reset:active { transform: scale(0.97); }`.
   - `.dock :global(.dock-icon)` (new rule): `transition: transform var(--v-dur-press) var(--v-ease-out);`. Plus `.dock a:active :global(.dock-icon) { transform: scale(0.95); }`.
4. **`src/routes/activity/[id]/+page.svelte`**: wrap `.rule-row:hover .rule-text` in the hover media query and add `.rule-row:active { background: var(--v-tint-fill); }`.
5. **`src/routes/+page.svelte`**: wrap `a.fig:hover .f-cap` and `.lead a:hover` in the hover media query and add `a.fig:active { background: var(--v-tint-fill); }`.
6. **`src/routes/login/+page.svelte`**: `.link-btn`: same scale press as step 1, hover in the media query.

## Boundaries

- Do NOT add press feedback to kit components (Button, Chip, SegmentedControl): they have their own.
- Do NOT add hover lift, shadow or scale to rows or cards. That is out of character with the hairline, shadowless look, and rows are hit too often.
- Do NOT change colours, sizes or markup.
- If an excerpt does not match, STOP and report.

## Verification

- **Mechanical**: `npm run check` and `npx playwright test` are green.
- **Feel check**:
  - Desk: press and hold an Activity row. A darker wash appears at once and leaves at once on release. Hover still tints and turns the title petrol.
  - Phone (DevTools device mode, then a real phone): tap a row and go back. No hover tint is stuck on it. No grey tap flash shows. A double tap does not zoom.
  - Press a filter. It dips to 0.97 and comes back. At 10% playback (Animations panel) the press uses the strong ease-out.
  - Reduced motion on: presses snap without the scale travel.
- **Done when**: every element in the table has its press, and every `:hover` in the edited files is gated.
