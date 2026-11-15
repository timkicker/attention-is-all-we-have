# 005 — Rows the agent adds slide in and glow; rows that are answered leave; the waiting count ticks

- **Status**: DONE
- **Commit**: 61a5322
- **Severity**: MEDIUM
- **Category**: Missed opportunities (state indication), Interruptibility
- **Depends on**: 001 (`collapse`, `.v-glow`, tokens)
- **Estimated scope**: 4 files, ~70 lines

## Problem

Home and Activity poll every 2 s (`live()`), which is the product's core promise: "an order the agent places shows up without a reload". When it does show up, it **teleports**. Every row below jumps down by 64 px in one frame and nothing marks the new row. The same happens in reverse when an approval elsewhere empties "Needs you". In a demo on a projector, the most important moment of the product goes unnoticed.

```svelte
<!-- src/routes/+page.svelte:150-151 — current -->
<ListSection id="latest" title="Latest" link={{ href: "/activity", label: "All activity" }}>
  {#each latest as i (i.id)}<ActivityRow item={i} />{/each}
</ListSection>
```

```svelte
<!-- src/routes/+layout.svelte:139 — the waiting count on Home's nav word, current -->
<span class="nb num" aria-hidden="true">{n}</span><span class="sr-only">, {n} waiting</span>
```

## Target

Svelte 5 transitions are **local** by default. An `in:` on an `{#each}` item plays only when that item is added to an each-block that already exists, never on the first render of the list. That is exactly "only rows that arrived while you watched". Do not add `|global`.

| Moment | Element | Motion |
|:---|:---|:---|
| A new row arrives | the row wrapper | `in:collapse` (height 0 to its height, opacity 0 to 1), 260 ms `--v-ease-out`, plus the class `v-glow` (petrol tint fading over 1200 ms after a 160 ms hold) |
| The rows below | siblings | pushed by the growing height in the same 260 ms. Together, one motion |
| A row leaves (answered, filtered out by status) | the row wrapper | `out:collapse` with `duration: 200`. Exits are shorter |
| A row changes place | the row wrapper | `animate:flip={{ duration: 260, easing: easeInOut }}` (movement on screen) |
| The waiting count changes | the `.nb` number | `{#key n}` with `in:blurSwap={{ y: 4 }}` (200 ms). The old number leaves without a transition |

Reduced motion: `collapse` and `blurSwap` already turn into 120 ms fades (plan 001). The glow still fades: it is colour, not movement.

## Repo conventions to follow

- Rows sit in `ListSection` (kit `Section` with class `v-card`). Hairlines between rows come from `src/app.css:318-320`:
  ```css
  .section.v-card > .section-card > * + * {
    border-top: 1px solid var(--v-line);
  }
  ```
  A wrapper `div` around each row becomes the direct child, so the hairline moves onto the wrapper and looks the same.
- Transitions are imported from `$lib/motion` (plan 001): `collapse`, `blurSwap`, `easeInOut`.

## Steps

1. **Create `src/lib/v2/LiveRows.svelte`**, a keyed list with arrive and leave motion:

   ```svelte
   <script lang="ts" generics="T extends { id: string }">
     /// A list the server can add to while it is on screen. Rows that arrive slide open and glow;
     /// rows that leave fold away; rows that move travel. The first render does not animate.
     import type { Snippet } from "svelte";
     import { flip } from "svelte/animate";
     import { collapse, easeInOut } from "$lib/motion";
     let { items, row }: { items: T[]; row: Snippet<[T]> } = $props();
   </script>

   {#each items as it (it.id)}
     <div
       class="lr"
       animate:flip={{ duration: 260, easing: easeInOut }}
       in:collapse
       out:collapse={{ duration: 200 }}
       onintrostart={(e) => (e.currentTarget as HTMLElement).classList.add("v-glow")}
     >
       {@render row(it)}
     </div>
   {/each}
   ```

   Svelte 5 dispatches `introstart` on the element (`onintrostart`). Confirm with the svelte-code-writer docs lookup. If it does not fire, add the class inside a custom wrapper transition instead.
2. **`src/routes/+page.svelte`**: replace the two each-loops:
   - Needs you: `{#each h.needsYou as i (i.id)} <div class="need" …>…</div> {:else}…{/each}` becomes `<LiveRows items={h.needsYou}>{#snippet row(i)}<div class="need" …>…</div>{/snippet}</LiveRows>`. Keep the `{:else}` "Nothing waits for you" line in an `{#if !h.needsYou.length}` after it.
   - Latest: `<LiveRows items={latest}>{#snippet row(i)}<ActivityRow item={i} />{/snippet}</LiveRows>`.
   - The `.need` row keeps its `border-left: 2px solid var(--valio)`.
3. **`src/routes/activity/+page.svelte`**: inside each day group, `<LiveRows items={g.items}>{#snippet row(i)}<ActivityRow item={i} />{/snippet}</LiveRows>`. A whole new day group (the first item of a new day) appears without its own animation. That is rare and acceptable.

   Interaction with plan 004: a filter switch replaces the list. Rows leaving would play `out:collapse` for every row. Wrap the whole `{#each byDay(...)}` in `{#key status}` so a filter change remounts the list without per-row exits (`#key` on a small list is fine).
4. **`src/routes/+layout.svelte`**: in the `waitCount` snippet:

   ```svelte
   {#snippet waitCount(n: number)}
     <span class="nb num" aria-hidden="true">{#key n}<span class="nb-n" in:blurSwap={{ y: 4 }}>{n}</span>{/key}</span><span class="sr-only">, {n} waiting</span>
   {/snippet}
   ```

   Add `.nb-n { display: inline-block; }`. The badge itself (`.nb`) appears and disappears as today, with no scale-from-zero.
5. Add `export { default as LiveRows } from "./LiveRows.svelte";` to `src/lib/v2/index.ts`.

## Boundaries

- Do NOT stagger rows. Do NOT animate rows on the first render or on a revisit.
- Do NOT animate the money or the time inside a row.
- Do NOT use the kit's `.badge-pop` class: it scales from 0.
- If `collapse` is missing from `$lib/motion`, plan 001 is not done. STOP.

## Verification

- **Mechanical**: `npm run check`, `npx playwright test`, `make e2e-live` (the demo scenes add rows while the page is open).
- **Feel check**:
  - Live mode: open Home and run `make agent SCENE=2` in another terminal. The new row slides open at the top of Latest and Needs you, tinted petrol, and the tint fades. Rows below glide down in the same motion. The nav badge number swaps with a soft blur.
  - Approve the waiting item on a phone or in a second tab. On the first tab, the row folds away and the badge changes. Nothing jumps.
  - Reload Home: no row animates.
  - At 10% playback: the growing row and the pushed rows move as one.
  - Reduced motion: rows fade in place (120 ms) and the glow still fades.
- **Done when**: additions and removals by polling never teleport, and first renders never animate.
