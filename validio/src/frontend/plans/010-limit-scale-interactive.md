# 010 — The limit scale: see the Rules as zones, drag the limits, see where an order landed

- **Status**: DONE
- **Commit**: 61a5322
- **Severity**: MEDIUM (the most "interactive" new element; it explains the product's core rule)
- **Category**: Missed opportunities (explanation, feedback), Gestures
- **Depends on**: 001
- **Estimated scope**: 1 new component, 3 pages, ~260 lines

## Problem

The core rule of Validio is spatial: below one amount the agent orders alone, up to a second one the order waits for you, and above that it is blocked. The app only ever says it in rows of text:

```svelte
<!-- src/routes/rules/+page.svelte — current -->
<ListRow id="rule-alone" label="Ordered alone" value={upTo(r.aloneUpToCents)} />
<ListRow id="rule-waiting" label="Waiting for you" value={upTo(r.approvalUpToCents)} />
<ListRow id="rule-blocked" label="Blocked" value="Above {money(r.approvalUpToCents)}" />
```

On Rules edit the owner types two numbers into separate fields and cannot see their relationship until a validation message says "Must not be above Waiting for you".

The request detail has a one-off meter (`src/routes/activity/[id]/+page.svelte:293-309`, `.meter`/`.fill`/`.tick`). It is static, animates `width` through `style:width` (a layout property), and does not share a look with anything else.

## Target

One component, `src/lib/v2/LimitScale.svelte`, used in three places:

| Place | Mode | What it shows |
|:---|:---|:---|
| Rules (view) | `read` | three zones with their amounts, above the Money rows |
| Rules edit | `edit` | the same zones with **two draggable handles**, synced two-way with the Ordered alone and Waiting for you fields |
| Request detail margin ("How this was checked") | `order` | the zones, plus a marker where this order's total landed, travelling in once |

**Geometry.** The scale runs from 0 to `max = max(approval × 1.25, order × 1.06, 100 €)`. The track is 8 px high (halbat's spend bar). There are three zone layers, each a full-width absolutely positioned `span` clipped to its part:

- alone: `background: var(--v-wash-ok)`, `clip-path: inset(0 calc(100% - A%) 0 0)`
- waiting: `background: var(--v-wash-wait)`, `clip-path: inset(0 calc(100% - W%) 0 A%)`
- blocked: `background: var(--v-wash-bad)`, `clip-path: inset(0 0 0 W%)`

`clip-path` changes go through `transition: clip-path var(--v-dur-ui) var(--v-ease-in-out)` (movement on screen), **disabled while dragging** (`.dragging .zone { transition: none }`) so they track the pointer 1:1. A thin 1 px boundary line at A% and W% uses `var(--v-fg)`.

Labels under the track, in `--fs-cap`, `--v-muted`, tabular: "Alone up to 1,200.00 €" at A%, "Waits up to 5,000.00 €" at W%, "Blocked above" at the right. Labels that would overlap fall back to a list under the bar (phone).

**Handles (edit mode).** Each handle is a `button`-sized hit area (24 × 32 px desk, 44 × 44 px phone), centred on its boundary and positioned with `transform: translateX(px)`, where px = fraction × the track width from `bind:clientWidth`. Never animate `left`. The visible grip is a 4 × 20 px bar `var(--v-fg)` with `border-radius: var(--radius-chip)`.

- `role="slider"`, `aria-label="Ordered alone"` or `"Waiting for you"`, `aria-valuemin`, `aria-valuemax`, `aria-valuenow` (cents), `aria-valuetext` (`money(c)`).
- Pointer: `pointerdown` calls `setPointerCapture`, adds `.dragging`, and records the start. `pointermove` maps x to cents 1:1. During the drag, snap to 10 € (1000 cents). On `pointerup`, snap to 50 € (5000 cents) with the transform transitioning `200ms var(--v-ease-out)`.
- **Friction instead of a hard stop**: alone may not pass waiting. Past the other handle, show only `overshoot × 0.2` of the movement, and on release spring back to the other handle's value through the same 200 ms ease-out.
- Keyboard: ←/→ ±50 €, Shift+←/→ ±500 €, Home = 0, End = the other bound. No animation on keyboard moves: they apply instantly (`transition: none` when the change came from a key; set a flag in the keydown handler).
- Pressed grip: `transform: scaleY(1.15)` over `var(--v-dur-press) var(--v-ease-out)`.
- Every change calls `onchange({ alone, waiting })`. The edit page writes `amountText(c)` into `f.alone` / `f.waiting`. Field edits flow back through props, and the zones animate with the 200 ms clip transition.

**Order marker (order mode).** A 2 px × 16 px `var(--valio)` line with a label "This order 1,515.00 €". Placed with `transform: translateX(px)`. First appearance: `@starting-style { transform: translateX(0px); opacity: 0 }` to its spot, `transition: transform var(--v-dur-moment) var(--v-ease-out), opacity var(--v-dur-ui) var(--v-ease-out)`. It travels from 0 to where the order sits, which is the explanation. Reduced motion: no travel, the fade only (`--v-dur-moment` is 120 ms, and translate from 0 is skipped with `@media (prefers-reduced-motion: reduce) { @starting-style { .mk { transform: translateX(var(--x)); } } }`; the executor sets `--x` with `style:--x` on the marker itself).

## Repo conventions to follow

- Washes: `--v-wash-ok`, `--v-wash-wait`, `--v-wash-bad` (tokens.css). No new colours.
- Money: `money()` from `$lib/v2`, `amountText()` / `parseAmount()` from `src/routes/rules/rules.ts`.
- Rules edit field ids `f-alone`, `f-waiting`, and the validation in `check()` stay. `e2e/rules.spec.ts` drives the fields, not the handles.

## Steps

1. Create `src/lib/v2/LimitScale.svelte` with props `{ alone: number; waiting: number; order?: number | null; mode: "read" | "edit" | "order"; onchange?: (v: { alone: number; waiting: number }) => void; id?: string }`. Build it as described above. Export it from `src/lib/v2/index.ts`.
2. `src/routes/rules/+page.svelte`: as the first child of `<ListSection id="money" …>`, add `<div class="ls-scale"><LimitScale mode="read" alone={r.aloneUpToCents} waiting={r.approvalUpToCents} id="rules-scale" /></div>` with `padding: 16px 0 20px`. The rows stay: screen readers and the e2e suite read them.
3. `src/routes/rules/edit/+page.svelte`: above the Money fields, add `<LimitScale mode="edit" alone={cents(f.alone) ?? 0} waiting={cents(f.waiting) ?? 0} onchange={(v) => { f.alone = amountText(v.alone); f.waiting = amountText(v.waiting); }} id="edit-scale" />`. When a field does not parse (`cents()` returns null), the scale keeps its last good value. Keep a `lastGood` `$state` in the page.
4. `src/routes/activity/[id]/+page.svelte`: replace the `.meter` and `.legend` markup inside `{#if limits}` with `<LimitScale mode="order" alone={limits.alone} waiting={limits.most} order={limits.total} id="detail-scale" />`. Keep the `<dt>` text ("Within your limits" etc.). Delete the `.meter`, `.fill`, `.tick` and `.legend` styles and the `scale`, `pct` and `short` helpers if they become unused.
5. Phone (≤760 px): the labels stack under the bar, the handles grow to 44 × 44 hit areas, and add `touch-action: none` on the handles only (the page keeps scrolling).

## Boundaries

- Do NOT remove the text rows or the fields. The scale is an additional view, not a replacement.
- Do NOT add per-week to this scale (a different dimension).
- Do NOT animate on keyboard input.
- No new dependencies.
- If an excerpt does not match, STOP and report.

## Verification

- **Mechanical**: `npm run check`. `npx playwright test e2e/rules.spec.ts e2e/activity-detail.spec.ts`. `make a11y` (the sliders need names, values and contrast of the zone boundaries).
- **Feel check**:
  - Rules edit, desk: drag the "Ordered alone" grip. The green zone follows the pointer exactly with no lag, and the field updates as you drag. Release: it settles on a 50 € step. Drag it past the second grip: it resists, then springs back.
  - Type `3000` into Waiting for you and tab out: the zones glide to the new boundary in 200 ms.
  - Arrow keys on a focused grip: instant 50 € steps, screen reader reads "1,250.00 €".
  - Phone (real device): the handles are easy to grab and vertical page scroll still works when swiping over the bar elsewhere.
  - Request R-4: the marker travels from the left to its spot once, ending inside the petrol zone.
  - Reduced motion: no travel, the marker fades in place.
- **Done when**: the Rules read as a picture, edit is draggable and keyboard-accessible, and the detail shows where the order landed.
