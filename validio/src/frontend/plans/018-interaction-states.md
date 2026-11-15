# 018 — One interaction-state system: hover, active, focus, busy, disabled, invalid, selected

- **Status**: DONE
- **Commit**: 61a5322
- **Severity**: HIGH
- **Category**: Cohesion, Accessibility, Physicality
- **Depends on**: 001, 002 (002 covers press and the hover media gate; this plan covers everything else and the matrix as a whole)
- **Estimated scope**: `src/app.css` plus ~8 components, ~180 lines

## Problem

States grew one rule at a time and do not agree:

- **Hover is inconsistent.** Running-text links fade their underline colour (`src/app.css:136-149`). Crumbs (`:165-172`), the section link (`src/lib/v2/ListSection.svelte:56-62`) and fold summaries (`src/app.css:694-697`) switch `text-decoration` from none to underline in one frame. Rows tint their background, and nav words change colour.
- **Focus is one global outline** (`src/app.css:11-21`):
  ```css
  :focus-visible {
    outline: 2px solid var(--valio);
    outline-offset: 2px;
  }
  ```
  On full-width rows inside a Section, the ring sits 2 px outside the row, over the hairlines and outside the section edge. A keyboard user gets the ring but none of the hover tint a mouse user sees. Inputs get the same detached ring instead of a field that looks active.
- **After navigation focus stays on `<body>`**. A screen reader or keyboard user starts from the top of the band every time.
- **Busy states are just `disabled`.** Save, Approve, Connect, Run and Log in turn grey at 50% and nothing says work is happening.
- **No caret, selection or anchor offset styling.** Text selection is the browser's blue. Anchors and `scrollIntoView` land under the sticky 60 px band (`#proof`, `#option-…`).

## Target: the state matrix

All colour changes use `var(--duration-fast)` (150 ms) `ease`, which is right for colour. Movement uses `--v-ease-out`. **Focus appears instantly**: it is keyboard-driven, and keyboard actions never animate. Every `:hover` sits inside `@media (hover: hover) and (pointer: fine)` (plan 002).

| Element | Hover | Active (002) | Focus-visible | Disabled / busy | Selected / current |
|:---|:---|:---|:---|:---|:---|
| Running-text link (`.link`, `.facts a`, `.lead a`, `.prose a`, `a.v-link`) | underline colour `--valio-underline` to `currentColor`, thickness `1px` to `2px` | colour `--valio-deep` | ring 2 px, offset 2 px, `border-radius: var(--radius-chip)` | — | — |
| Quiet link (`.crumbs a`, `.ls-link`, `details.fold > summary`, `.db-reset`, `.link-btn`) | **always underlined** with `text-decoration-color: transparent`, turning `currentColor` on hover, so it fades in instead of popping | scale 0.97 | the same ring | — | — |
| Row link (`a.ar`, `a.vr`, `a.v-row`, `.rule-row`, `a.fig`) | background `--v-tint-hover`, title `--valio`. The trailing chevron `.go` nudges `translateX(2px)`, 150 ms `--v-ease-out` | background `--v-tint-fill` | **inset** ring (`outline-offset: -2px`) **plus the hover background and title colour** | — | — |
| Nav word, dock tab | colour to `--valio-band-fg` / `--valio` (existing) | icon 0.95 | ring offset `-2px`, colour `--valio-band-fg` on the band | — | travelling ink (015) |
| Filter button | colour `--v-fg` | 0.97 | ring offset 2 px | — | ink bar (015) |
| Kit Button | kit + app.css (existing) | kit 0.97 | ring offset 2 px (existing) | `busy`: spinner + label (below), `aria-busy="true"`, `cursor: progress` | — |
| Text field (`[data-slot="input"]`) | border `--v-line-strong` to `--v-fg` | — | border `--valio` **and** outline 2 px `--valio` offset 0 (field and ring as one edge). The label above turns `--v-fg` through `.vf:focus-within label` | `opacity` per kit | invalid: border `--v-bad`, ring `--v-bad` when focused |
| Option table row (`.opts tbody tr`) | tint (existing) | — | rows are not focusable: no change | — | chosen: existing petrol rule |
| Proof hash button (011) | underline fades in as for quiet links | 0.97 | ring | — | — |

### Busy (one pattern for every async button)

`src/lib/v2/BusyLabel.svelte`: `<BusyLabel busy={busy} idle="Save" working="Saving" />` renders the label, plus while `busy` a lucide `LoaderCircle` 14 px before it, rotating `animation: v-spin 800ms linear infinite` (constant motion, so linear). The spinner fades in after a **300 ms delay** (`animation: v-fade-in 150ms ease 300ms both`), so a fast answer never flashes it. The working word swaps through `blurSwap`. The button's `min-width` is fixed to its idle width (measured once with `bind:offsetWidth` on mount) so nothing shifts. Reduced motion: the spinner does not rotate (a static icon and the working word carry the meaning).

Where: approve `code-submit` ("Approve" / "Approving"), Rules Save ("Save" / "Saving"), Settings `Form` Save, Agent Connect / Allow / Pause ("Connecting", "Allowing", "Pausing"), Login submit ("Log in" / "Logging in", "Create account" / "Creating"), "Try the demo kitchen" / "Opening", token dialog Run / "Running". Copy stays short with no dashes.

### Global details

- `::selection { background: var(--valio-tint-strong); color: var(--v-fg); }`
- `input, textarea { caret-color: var(--valio); }`, plus `accent-color: var(--valio)` on `:root` for any native checkbox or radio.
- `html { scroll-padding-top: 76px; }` (band 60 + 16). At ≤760 px: `64px`. Anchors, `scrollIntoView({ block: "start" })` and focus moves then clear the sticky band.
- **Focus after navigation**: in `+layout.svelte`, `afterNavigate(({ type }) => { if (type !== "enter") document.querySelector<HTMLElement>("h1.v-title")?.focus({ preventScroll: true }); })`, with `tabindex="-1"` on `h1.v-title` in `VHead.svelte`. The `:focus:not(:focus-visible)` rule keeps it ringless for mouse users. Skip this when the navigation came from a filter (same path).

## Repo conventions to follow

- Tokens: `--valio`, `--valio-deep`, `--valio-underline`, `--valio-tint-strong`, `--v-tint-hover`, `--v-tint-fill`, `--v-line-strong`, `--v-bad`, `--radius-chip`. No literals (`check-tokens.mjs`).
- Kit components stay untouched. Their states are restyled from `src/app.css` with `[data-slot=…]` selectors, as the file already does (`src/app.css:25-60`).

## Steps

1. `src/app.css`:
   - Links: in the `.link, .facts a, .lead a, .prose a` rule add `text-decoration-thickness: 1px; transition: color var(--duration-fast) ease, text-decoration-color var(--duration-fast) ease, text-decoration-thickness var(--duration-fast) ease;`. On hover add `text-decoration-thickness: 2px`. Add `a.v-link` to both selectors. Add `:active { color: var(--valio-deep); }`.
   - Quiet links: `.crumbs a`, `details.fold > summary`, and in components `.ls-link`, `.db-reset`, `.link-btn` become `text-decoration: underline; text-decoration-color: transparent; text-underline-offset: 3px; transition: text-decoration-color var(--duration-fast) ease, color var(--duration-fast) ease;`. Hover sets `text-decoration-color: currentColor`.
   - Rows: `a.v-row:focus-visible, a.vr:focus-visible { outline-offset: -2px; background: var(--v-tint-hover); }` and `a.v-row:focus-visible .v-row-title, a.vr:focus-visible .vr-value { color: var(--valio); }`. Chevron: `.v-row-end .go { transition: transform var(--duration-fast) var(--v-ease-out); }`, `a.vr:hover .go { transform: translateX(2px); }` (inside the hover media query).
   - Inputs: `[data-slot="input"] { transition: border-color var(--duration-fast) ease; }`, hover border `var(--v-fg)`, `[data-slot="input"]:focus-visible { border-color: var(--valio); outline-offset: 0; }`, `[data-slot="input"][aria-invalid="true"] { border-color: var(--v-bad); } [data-slot="input"][aria-invalid="true"]:focus-visible { outline-color: var(--v-bad); }`.
   - Global details as listed. A `@keyframes v-spin { to { transform: rotate(360deg); } }` and `@keyframes v-fade-in { from { opacity: 0; } }`.
2. `src/lib/v2/ActivityRow.svelte`: `.ar:focus-visible { outline-offset: -2px; background: var(--v-tint-hover); } .ar:focus-visible .ar-title { color: var(--valio); }`. The same pattern for `.rule-row` (activity detail), `a.fig` (Home) and `.topnav a` / `.dock a` (layout; colour `--valio-band-fg` on the band).
3. `src/lib/v/VField.svelte`: `.vf label { transition: color var(--duration-fast) ease; color: var(--v-muted); } .vf:focus-within label { color: var(--v-fg); }`. Check the current label colour first. If it is already `--v-fg`, invert: muted at rest is only right if contrast stays ≥4.5:1 (`--v-muted` on white is about 5.3:1, fine).
4. Create `src/lib/v2/BusyLabel.svelte` as described. Export it and use it in every button listed above.
5. `src/lib/v/VHead.svelte`: `tabindex="-1"` on `h1.v-title`. `src/routes/+layout.svelte`: the `afterNavigate` focus move, skipping same-path navigations (`from?.url.pathname === to?.url.pathname`).

## Boundaries

- Do NOT animate the focus ring (no growing outline, no glow ring).
- Do NOT restyle kit internals beyond `[data-slot]` hooks already in use.
- Do NOT change any copy except the busy words.
- If an excerpt does not match, STOP and report.

## Verification

- **Mechanical**: `npm run check`, `npx playwright test`, `make a11y` (focus order, names, contrast of the inset ring on tinted rows: `--valio` on `--v-tint-hover` must be ≥3:1).
- **Feel check**:
  - Tab through Home, Activity and a request: every row shows the ring *inside* its edges plus the same tint as hover. The ring never overlaps a neighbour's hairline.
  - Hover the crumbs, "All activity" and a fold summary: the underline fades in, never pops.
  - Click into a field: the border turns petrol and the label darkens. Make it invalid: red border, red ring.
  - On a slow network (Fast 4G), Save on Rules edit: under 300 ms nothing but the word changes. After that the spinner fades in. The button never changes width.
  - Navigate with the keyboard: after each page change, Tab starts at the page title, not in the band.
  - Select text: a petrol selection. "See the proof": the summary lands below the band, not under it.
- **Done when**: every interactive element answers hover, press and focus the same way as its siblings, and busy work is always visible.
