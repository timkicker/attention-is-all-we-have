# 023 — Explain in place: popovers for terms, tooltips for cut-off text

- **Status**: DONE
- **Commit**: 61a5322
- **Severity**: LOW
- **Category**: Physicality & origin (popovers), new interaction
- **Depends on**: 001, 018
- **Estimated scope**: 2 new components, ~6 places, ~120 lines

## Problem

Validio has words a new kitchen does not know: "sealed" (Proof summary), "Rules, version 3" (detail), "Delivered in full" (an options column), "Per week, before VAT" (Rules), "Spend Pass" (Agent versions). Each is either unexplained or explained by a sentence that sits on screen permanently. Cut-off text has no way to be read in full: the kitchen name in the band (`.k-name`, `text-overflow: ellipsis`, `max-width` 140 to 240 px) and long product names on the phone.

The kit has both pieces (`@arlen/ui-kit/components/ui/popover`, `…/tooltip`). Its popover animates with `zoom-in-95` and a slide, but from the centre. Its tooltip waits 1500 ms every time (`tooltip/tooltip.svelte:23`).

## Target

### A. `Explain` (an info popover)

`<Explain label="What sealed means">Each entry carries the fingerprint of the one before. A changed entry breaks the chain.</Explain>`

- Trigger: a 20 × 20 px button (44 × 44 hit area on the phone, through padding) with lucide `Info` 14 px in `--v-faint`, turning `--valio` on hover and focus. `aria-label` from `label`.
- Content: kit `Popover.Content`, max-width 280 px, `--fs-meta`, `--v-fg` on `--v-surface`, 1 px `--v-line-strong` border, `--radius-card`, padding 12 px 14 px, no shadow.
- **Motion from the trigger**: override the transform origin to bits-ui's computed origin, so it grows out of the icon:
  ```css
  [data-slot="popover-content"] { transform-origin: var(--bits-popover-content-transform-origin); }
  ```
  Timing: enter 160 ms `var(--v-ease-out)`, exit 120 ms. Override the tw-animate duration through `animation-duration` on `[data-state="open"]` / `[data-state="closed"]`. Check the kit's attribute names (`data-open`/`data-closed` per `popover-content.svelte:21`).
- Click to open, click outside or Escape to close (bits-ui does this).
- Two sentences maximum. Plain words, no dashes.

### B. Tooltips for cut-off text, with skip-delay

- A `Truncate` wrapper: renders the text with ellipsis, and only when the text is actually cut (`scrollWidth > clientWidth`, re-measured on resize) wraps it in a kit Tooltip showing the full text.
- **Delay**: the first tooltip waits **500 ms**. Any tooltip opened within **300 ms** of another closing opens **instantly, with no animation** (Emil's rule: after the first, tooltips in a group are instant). Implement with a module-level `lastClosedAt` and the kit's `instant` prop (`tooltip.svelte:23` derives `delay` from it).
- Tooltip motion when not instant: 125 ms `var(--v-ease-out)`, `scale(0.97) → 1` plus fade, origin at the trigger. Instant ones: no animation (`animation: none` when `data-instant` is set by the wrapper).
- Touch: tooltips do not open on tap (the kit's bits-ui default). On the phone, the full kitchen name is in Settings anyway.

### Where

| Place | Piece | Copy |
|:---|:---|:---|
| Proof summary "N entries, sealed" (`activity/[id]/+page.svelte:273`) | Explain | "Each entry carries the fingerprint of the one before. A changed entry breaks the chain." |
| "Rules, version N" (`:249`) | Explain | "Every Rules save signs a new version. Orders show the version they were decided under." |
| Options header "Delivered in full" (`Options.svelte`, the `v-th`) | Explain | "How often Valio delivered this product in full lately." |
| Rules "Money, before VAT" heading | Explain | "Limits count Valio's catalog prices before VAT." |
| Agent "What it may do" | Explain | "These come from your Rules. Change them there and the agent follows." |
| Band `.k-name`, Home `.need-title` and `.ar-title` on the phone | Truncate | the full text |

## Repo conventions to follow

- Kit imports: `import * as Popover from "@arlen/ui-kit/components/ui/popover"`, `import * as Tooltip from "@arlen/ui-kit/components/ui/tooltip"`. Check the index files for exact names (`Root`, `Trigger`, `Content`).
- Restyle kit pieces only through `[data-slot]` and `data-*` state selectors in `src/app.css`, as the file already does.

## Steps

1. Create `src/lib/v2/Explain.svelte` and `src/lib/v2/Truncate.svelte` and export both.
2. Add the popover and tooltip overrides to `src/app.css`, with reduced motion: `animation-duration: 120ms` and no zoom (`--tw-enter-scale: 1`; check the variable name tw-animate uses).
3. Place them per the table.

## Boundaries

- No hover-only information: every Explain opens on click and focus as well.
- No tooltip on elements whose text is not cut.
- Do not change the existing sentences on the page. Explain adds, it does not move copy.

## Verification

- **Mechanical**: `npm run check`, `npx playwright test`, `make a11y` (the buttons have names, and the popover is reachable and closes with Escape).
- **Feel check**: click the info icon by "sealed". The popover grows out of the icon, not from its middle (10% playback). Hover a cut-off kitchen name: after half a second its full name appears. Move to another cut-off title right away: it shows instantly.
- **Done when**: every unfamiliar term can be explained in place, and nothing cut off is unreadable.
