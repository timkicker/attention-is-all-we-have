# 022 — Reading aids: a price ladder, sticky day heads, find in Activity

- **Status**: DONE
- **Commit**: 61a5322
- **Severity**: LOW
- **Category**: New interaction (no motion on data)
- **Depends on**: 018 (focus and hover states). Plan 013's `/` key focuses the find field if 013 is done
- **Estimated scope**: 3 files, ~140 lines

## Problem

1. **Options are hard to compare.** The options table (`src/routes/activity/[id]/Options.svelte`) lists totals as numbers only. Seeing that the chosen product is 90 € cheaper than the next means reading and subtracting.
2. **Day heads scroll away.** In a long Activity list, after the first screen you no longer know which day a row is from (`src/routes/activity/+page.svelte:70-78`, `.dg .v-h`).
3. **No way to find an item.** An owner who remembers "the mozzarella one" scrolls through every day.

## Target

### A. Price ladder (Options, Total column)

Under each suitable option's total, a 3 px bar: `transform: scaleX(total / maxTotal)`, `transform-origin: right` (the column is right-aligned, so bars grow toward the number). Colours: the chosen row `var(--valio)`, the others `var(--v-line-strong)`. **No animation**: this is data being compared. Hide it at ≤760 px, where the table folds into lines.

Hovering a row (pointer fine only) shows the difference to the chosen option in the row's sub line, e.g. "90.00 € more". This uses the existing `whyNot()` text when present, so no new computation is needed when `whyNotText` exists. The swap uses `blurSwap` 160 ms. That is frequent, but it is a hover detail, and the swap is the only thing that moves.

### B. Sticky day heads (Activity)

`.dg .v-h { position: sticky; top: 60px; z-index: 2; background: var(--v-ground); }` (`top: 52px` at ≤760 px, the phone band height). When a head is stuck, it gets a 1 px bottom border `var(--v-line)`. Detect it with a zero-height sentinel before each head and an `IntersectionObserver` (`rootMargin: "-61px 0px 0px 0px"`), toggling a `stuck` class. The border colour changes over 150 ms `ease`. No movement.

### C. Find in Activity

A field above the list on the right of the filters row: `<input type="search" placeholder="Find" aria-label="Find in activity">`, `--height-control`, 200 px desk. On the phone it sits under the filters at full width.

- Filters the loaded items client-side, as you type, across `title` and `why`, case- and accent-insensitive (`normalize("NFD").replace(/\p{Diacritic}/gu, "")`).
- Matches are highlighted with `<mark>`: `background: var(--valio-tint); color: inherit; border-radius: var(--radius-chip); padding: 0 2px`.
- **No animation while typing** (a keyboard action): wrap the list in `{#key query}`, so plan 005's row exits do not play for every keystroke.
- Empty result: the existing `Empty` component, "Nothing matches" with the detail "Try another word".
- The query lives in the URL (`?q=`, kept alongside `?status=`, `replaceState: true`, so Back does not walk every keystroke).
- `Escape` inside the field clears it.

## Repo conventions to follow

- Tokens only. `--valio-tint`, `--v-line`, `--v-line-strong`, `--v-ground`, `--radius-chip`.
- Copy: "Find", "Nothing matches", "Try another word", "90.00 € more".
- Keep the filters' ids and `aria-pressed`. `e2e/activity.spec.ts` covers them.

## Steps

1. `Options.svelte`: compute `const maxTotal = $derived(Math.max(...suitable.map((o) => o.totalCents ?? 0), 1))`. In the Total cell, under the number, add `<span class="ladder" class:mine={isChosen} style:transform="scaleX({(o.totalCents ?? 0) / maxTotal})" aria-hidden="true"></span>`, styled `display: block; height: 3px; margin-top: 4px; background: var(--v-line-strong); transform-origin: right;` and `.ladder.mine { background: var(--valio); }`. Add the hover swap on `.p-sub`.
2. `src/routes/activity/+page.svelte`: the sentinel and observer (set up with `{@attach}` on each sentinel, cleaned up on detach), plus the sticky CSS.
3. Same file: the find field, `query` derived from `page.url.searchParams.get("q") ?? ""`, filtering before `byDay()`, and a `highlight(text, q)` helper in `src/lib/v2/format.ts` that returns parts for safe rendering (`{#each parts as p}{#if p.hit}<mark>{p.text}</mark>{:else}{p.text}{/if}{/each}`). No `{@html}`.
4. `ActivityRow.svelte`: accept an optional `query` prop and render title and why through `highlight`.

## Boundaries

- No animation on the ladder or on typing.
- No server search. Client-side over what `api.activity()` returned.
- No `{@html}` for highlighting.

## Verification

- **Mechanical**: `npm run check`, `npx playwright test`. A new spec: type "mozz" on Activity, expect only matching rows with a `<mark>`, Escape restores all. The URL holds `q=mozz`.
- **Feel check**: on a request with options, you can see at a glance which option is cheapest, without reading digits. Scroll a long Activity: the day head stays under the band and gains its hairline only when stuck. Typing in Find filters instantly with nothing sliding.
- **Done when**: comparing, orienting and finding take no reading effort.
