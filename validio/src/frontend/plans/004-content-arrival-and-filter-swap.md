# 004 — Content arrives instead of popping; skeletons only when they are worth showing; filters keep their list

- **Status**: DONE
- **Commit**: 61a5322
- **Severity**: MEDIUM
- **Category**: Missed opportunities (preventing a jarring change)
- **Depends on**: 001, 003 (`live().fromCache`)
- **Estimated scope**: 7 files, ~60 lines

## Problem

1. **The skeleton flashes on fast answers.** `VState kind="loading"` (`src/lib/v/VState.svelte`) renders kit `Skeleton`s at once. The fixture answers in about 0 to 150 ms, so most visits show a single grey frame and then the page: a flicker, not a loading state.
2. **Loaded content replaces the skeleton in one frame.** For example, in `src/routes/+page.svelte:96-101`:

   ```svelte
   {#if home.error && !home.data}
     <LoadError detail={home.error} />
   {:else if !home.data}
     <Loading />
   {:else}
   ```
3. **Every filter click blanks the list.** `src/routes/activity/+page.svelte:63-66` shows `<Loading />` whenever the answer is for another filter:

   ```svelte
   {:else if !list.data || !fresh}
     <Loading />
   ```

   Filters are pressed tens of times a day. The list jumps to a skeleton and back each time.

## Target

1. **Skeleton delay**: the loading block fades in only after 150 ms. A faster answer never shows it.
   ```css
   .sk { animation: v-sk-in var(--v-dur-ui) var(--v-ease-out) 150ms both; }
   @keyframes v-sk-in { from { opacity: 0; } }
   ```
2. **One entrance per page**: the container holding loaded content gets `.v-arrive` (fade plus `--v-rise` travel, `--v-dur-enter`, `--v-ease-out`; defined in plan 001), but only when the data came from a fetch and not from the cache (`!x.fromCache`). A cached revisit is covered by the page transition (plan 003), and two entrances on one container are forbidden.
3. **Filters keep the old list** until the new one answers. It dims to `opacity: 0.55` with `transition: opacity var(--v-dur-ui) var(--v-ease-out)` and `aria-busy="true"`. When the answer comes, the new rows replace it at full opacity with **no** entrance animation, because this is high-frequency. With plan 003's cache, a filter already seen once switches instantly.

## Repo conventions to follow

- The shared state components are `src/lib/v2/{Loading,Empty,LoadError}.svelte`, wrapping `src/lib/v/VState.svelte`.
- Exemplar of a page's state switch: `src/routes/rules/+page.svelte` (`{#if data.error && !data.data}… {:else if !r}<Loading rows={4} />{:else}`).

## Steps

1. **`src/lib/v/VState.svelte`** `<style>`: add the `.sk` animation and keyframes above. The `{#if secs >= 10}` "Still loading" line stays as is.
2. **Pages**: on the element that wraps the loaded branch, add `class:v-arrive={!X.fromCache}`, where `X` is the page's `live` state:
   - `src/routes/+page.svelte`: `<div class="blocks" class:v-arrive={!!home.data && !home.fromCache}>`. The class goes on `.blocks` itself. A `display: contents` wrapper would not animate.
   - `src/routes/activity/[id]/+page.svelte`: `<div class="doc" class:v-arrive={!detail.fromCache}>`, plus the `.ask` block.
   - `src/routes/rules/+page.svelte`: `.blocks` as on Home.
   - `src/routes/agent/+page.svelte`: `.blocks`, with `class:v-arrive={!!a && !ag.fromCache}`.
   - `src/routes/settings/+page.svelte`: settings uses `onMount(load)` and not `live()`. Add `class:v-arrive={!!s}` on its content wrapper. It has no cache, so it always arrives.
   - `src/routes/rules/edit/+page.svelte`: same as settings (`r` set by `fill`).
3. **`src/routes/activity/+page.svelte`**:
   - Replace `{:else if !list.data || !fresh}` with `{:else if !list.data}`. The rows then render from `list.data.items` even when `!fresh`.
   - On `<div class="days">` add `class:stale={!fresh}` and `aria-busy={!fresh}`.
   - Style:
     ```css
     .days { transition: opacity var(--v-dur-ui) var(--v-ease-out); }
     .days.stale { opacity: 0.55; }
     ```
   - The Empty branch must use the fresh status. Change it to `{:else if fresh && !list.data.items.length}`, so the old filter's empty state does not show under the new filter's name.
   - The counts in the filter buttons stay as they are.

## Boundaries

- Do NOT stagger rows on any page. These lists are revisited many times a day.
- Do NOT add `.v-arrive` to elements inside a container that already has it.
- Do NOT change the Loading component's markup or the kit Skeleton.
- If an excerpt does not match, STOP and report.

## Verification

- **Mechanical**: `npm run check`, `npx playwright test` (`activity.spec.ts` covers the filter switch), `make a11y`.
- **Feel check**:
  - In DevTools set Network to "Fast 4G" (live mode) and open Home. The skeleton appears after a short beat, then the page rises 6 px into place in one move.
  - With no throttling, open Rules: no grey flash, only the rise.
  - Activity: click Waiting, then Blocked, then All quickly. The list dims and swaps and never shows a skeleton. Back to a seen filter is instant.
  - Navigate Home, then Activity, then Home: the second Home shows no rise, only the page crossfade (plan 003).
  - Reduced motion: the rise becomes a 120 ms fade.
- **Done when**: no visible skeleton on fast answers, one entrance per fresh page, and filter switches never blank the list.
