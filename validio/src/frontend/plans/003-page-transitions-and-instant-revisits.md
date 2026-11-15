# 003 — Page transitions with View Transitions, a title that travels into its detail, instant revisits

- **Status**: DONE
- **Commit**: 61a5322
- **Severity**: MEDIUM
- **Category**: Missed opportunities (spatial consistency), perceived performance
- **Depends on**: 001
- **Estimated scope**: 6 files, ~140 lines

## Problem

1. **Every navigation teleports.** The content under the band is swapped in one frame. Going from the Activity list into a request is the main reading path of the app, and nothing shows that the detail *is* the row you clicked.
2. **Every page starts empty.** `live()` (`src/lib/live.svelte.ts:9-31`) begins with `data: undefined`, so each visit, Back included, shows the skeleton again even though the same data was on screen a second ago:

   ```ts
   // src/lib/live.svelte.ts:11 — current
   const s = $state({ data: undefined as T | undefined, error: "", status: 0, loaded: false });
   ```
3. The detail title is `d?.item.title ?? ""` (`src/routes/activity/[id]/+page.svelte:162`). It stays blank until the detail answers, although the clicked row already knew the title.

## Target

**A. Stale-while-revalidate in `live()`.** Keep each page's last answer in memory, keyed by account and page. A revisit renders it at once and refetches as before. Clear the memory on `bump()` (a demo reset) and on any change of account.

**B. View Transitions on navigation** (Chrome, Edge and Safari 18+; elsewhere nothing changes):

| Element | Role | Motion |
|:---|:---|:---|
| Content column `.v-main .wrap` (`view-transition-name: v-page`) | Lead | old: opacity to 0, 140 ms `--v-ease-out`. New: from opacity 0 and `translateX(var(--v-page-dx))` to rest, 200 ms `--v-ease-out` |
| Band `.band`, demo strip, dock | Static | `view-transition-name: v-band / v-dock`, animation none |
| Detail title: the clicked row's `.ar-title` and then the detail `h1` (`view-transition-name: v-title`) | Lead (shared) | the group morphs position and size, 260 ms `--v-ease-in-out` (movement on screen) |

`--v-page-dx` follows direction: `12px` going deeper (list to detail), `-12px` going back up, `0px` between top-level pages, where the page only fades.

A navigation that changes only the query (Activity filters, `/rules?saved`) gets **no** view transition. Filters are hit tens of times a day (plan 004 handles them).

Under reduced motion, `onNavigate` does not start a transition at all.

**C. Peek:** the detail page shows the title it already knows from the list while the full detail loads.

## Repo conventions to follow

- Page-wide state lives in small `*.svelte.ts` modules (`src/lib/chrome.svelte.ts`, `src/lib/owner.svelte.ts`). Follow that.
- `bump()` in `chrome.svelte.ts` is the existing "everything is stale" signal.
- Keep every `id` and `data-testid`. The e2e suite depends on them.

## Steps

1. **`src/lib/live.svelte.ts`**: change the signature to `live<T>(fn: () => Promise<T>, ms = 2000, key?: () => string)`. Add a module-level cache:

   ```ts
   import { session } from "./owner.svelte";
   const cache = new Map<string, unknown>();
   /** Forget every page's last answer (a demo reset, another account). */
   export function forgetLive() {
     cache.clear();
   }
   ```

   Inside `live`, compute `const k = () => (key ? `${session.account?.id ?? "-"}:${key()}` : "")`. Before the first fetch, if `k()` is set and the cache has it, seed `s.data` with the cached value and set `s.loaded = true`. After each successful fetch, `cache.set(k(), data)`. Add `fromCache: boolean` to the state: true while the shown data came from the cache, false once a fetch answered. Plan 004 uses it.

   `key()` must be read inside the `$effect`, next to the existing `fn()` call, so a param change (a new status, a new id) also changes the key.
2. **`src/lib/chrome.svelte.ts`**: `bump()` calls `forgetLive()` before `chrome.version += 1`. Import it from `./live.svelte`. Watch for a circular import: live.svelte.ts imports chrome. If the cycle bites, move `forgetLive` and `cache` into a new `src/lib/live-cache.ts` that both import.
3. **`src/lib/owner.svelte.ts`** has no logic. In `src/routes/settings/sections.ts` `logOut()` and in `src/routes/login/+page.svelte` `done()`, call `forgetLive()`.
4. **Keys**: `src/routes/+page.svelte` `live(() => api.home(), 2000, () => "home")`. `src/routes/activity/+page.svelte` key `() => `activity:${status}``. `src/routes/activity/[id]/+page.svelte` detail key `() => `item:${id}``, request key `() => `request:${id}``. Agent page `() => "agent"`. Rules page `() => "rules"`. Home's and detail's `rules` live: `() => "rules-raw"`.
5. **Peek**: create `src/lib/peek.svelte.ts`:

   ```ts
   import type { ActivityItem } from "./api/types";
   /** The rows the lists last showed, so a detail can show its title before its own answer. */
   export const peek = new Map<string, ActivityItem>();
   /** The row whose title travels into the next page's heading. */
   export const morph = $state({ id: "" });
   ```

   In `src/lib/v2/ActivityRow.svelte`, call `peek.set(item.id, item)` in the script body. It is a plain Map, so the write in an `$effect.pre` or at the top level is fine. Add `onclick={(e) => { if (!e.metaKey && !e.ctrlKey && !e.shiftKey && e.button === 0) morph.id = item.id; }}` on the `<a>`. Give `.ar-title` `style:view-transition-name={morph.id === item.id ? "v-title" : undefined}`.

   In `src/routes/activity/[id]/+page.svelte`, add `const head = $derived(d?.item ?? peek.get(id));` and use `head?.title` for `PageHead title` and `head` for `here` (`longDay(head.at)`). Keep `missing` and everything else on `d`.
6. **`src/lib/v/VHead.svelte`**: accept a new prop `morphName?: string` and put `style:view-transition-name={morphName}` on `h1.v-title`. In the detail page pass `morphName={morph.id === id ? "v-title" : undefined}`.
7. **`src/routes/+layout.svelte`**, script:

   ```ts
   import { onNavigate } from "$app/navigation";
   import { reduced } from "$lib/motion";
   import { morph } from "$lib/peek.svelte";

   const depth = (p: string) => p.split("/").filter(Boolean).length;
   onNavigate((nav) => {
     if (!document.startViewTransition || reduced() || !nav.to || !nav.from) return;
     if (nav.from.url.pathname === nav.to.url.pathname) return; // a filter or ?saved: no page move
     const a = depth(nav.from.url.pathname), b = depth(nav.to.url.pathname);
     document.documentElement.dataset.navDir = b > a ? "deeper" : b < a ? "up" : "across";
     return new Promise<void>((resolve) => {
       const t = document.startViewTransition(async () => {
         resolve();
         await nav.complete;
       });
       t.finished.finally(() => {
         morph.id = "";
         delete document.documentElement.dataset.navDir;
       });
     });
   });
   ```

   Markup: add `style:view-transition-name="v-band"` on `<header class="band">`, `"v-dock"` on `<nav class="dock">`, `"v-demo"` on `.demobar`. Add `class="wrap"` content naming through CSS (step 8).
8. **`src/app.css`**, append:

   ```css
   /* ---------- page transitions (plans/003) ---------- */
   .v-main .wrap {
     view-transition-name: v-page;
   }
   :root[data-nav-dir="deeper"] { --v-page-dx: 12px; }
   :root[data-nav-dir="up"] { --v-page-dx: -12px; }
   :root[data-nav-dir="across"] { --v-page-dx: 0px; }
   ::view-transition-old(root),
   ::view-transition-new(root) {
     animation-duration: 160ms;
     animation-timing-function: var(--v-ease-out);
   }
   ::view-transition-group(v-band),
   ::view-transition-group(v-dock),
   ::view-transition-group(v-demo),
   ::view-transition-old(v-band),
   ::view-transition-new(v-band),
   ::view-transition-old(v-dock),
   ::view-transition-new(v-dock),
   ::view-transition-old(v-demo),
   ::view-transition-new(v-demo) {
     animation: none;
   }
   ::view-transition-group(v-page) {
     animation-duration: 200ms;
     animation-timing-function: var(--v-ease-out);
   }
   ::view-transition-old(v-page) {
     animation: v-page-out 140ms var(--v-ease-out) both;
   }
   ::view-transition-new(v-page) {
     animation: v-page-in 200ms var(--v-ease-out) both;
   }
   @keyframes v-page-out {
     to { opacity: 0; }
   }
   @keyframes v-page-in {
     from { opacity: 0; transform: translateX(var(--v-page-dx, 0px)); }
   }
   ::view-transition-group(v-title) {
     animation-duration: 260ms;
     animation-timing-function: var(--v-ease-in-out);
   }
   ::view-transition-old(v-title),
   ::view-transition-new(v-title) {
     animation-duration: 260ms;
     animation-timing-function: var(--v-ease-in-out);
     height: 100%;
     object-fit: contain;
     object-position: left center;
   }
   ```

## Boundaries

- Do NOT animate the band, the dock or the demo strip on navigation. They are the frame.
- Do NOT start a view transition for a same-path navigation.
- Do NOT add a page-level entrance (`.v-arrive`) to a page that is in a view transition. Plan 004 gates that with `fromCache`.
- No new dependencies.
- If an excerpt does not match, STOP and report.

## Verification

- **Mechanical**: `npm run check`, `npx playwright test` (runs with reduced motion, so no transition), and `make e2e-live` are green.
- **Feel check** (Chrome, the fixture `make demo-mock`):
  - Activity, then click "Grated Maestrella". The row's title travels and grows into the page title while the rest crossfades with a 12 px push from the right. Use the Animations panel at 10%: the title moves along an ease-in-out path, and it does not stretch or blur badly. If it smears, try `object-fit: none` on old/new.
  - Back (browser or "Activity" crumb): the list is there at once from the cache, with no skeleton. It pushes from the left.
  - Home to Rules: a quick crossfade only. Band and dock do not flicker.
  - Click a filter: no page transition.
  - Spam-click two rows fast: the second navigation skips the first transition cleanly, with no stuck title.
  - Reduced motion: navigation is instant.
  - Safari 17 / Firefox: navigation works exactly as before.
- **Done when**: list to detail morphs the title, revisits show cached data at once, and the frame never animates.
