# 020 — Feels live: a connection mark in the band, "just now" times, and details that open instantly

- **Status**: DONE
- **Commit**: 61a5322
- **Severity**: MEDIUM
- **Category**: Perceived performance, state indication
- **Depends on**: 001, 003 (the live cache)
- **Estimated scope**: 5 files, ~140 lines

## Problem

1. Validio polls every 2 s, but nothing on screen says the page is live. When the backend stops answering (the Modal container cold-starts, Wi-Fi drops), the page silently shows old data. Only a page without data shows `LoadError`.
2. Times in rows are clock times (`hm(item.at)` in `src/lib/v2/ActivityRow.svelte:30`). An order that arrived 5 seconds ago reads "14:02", the same as one from this morning.
3. Opening a request always waits for two requests (`api.activityItem`, `api.request`) after the click, although the pointer rested on the row for a few hundred milliseconds first.

## Target

### A. Live mark (band, desk and phone)

A small status mark before the kitchen name: a 6 px square (`border-radius: var(--radius-chip)`) and a word in `--fs-cap`.

| State | When | Mark | Word |
|:---|:---|:---|:---|
| Live | the last poll answered within the last 6 s | `var(--valio-band-fg)` | "Live" |
| Catching up | the last poll failed, or none answered for 6 s | `var(--valio-band-muted)`, outline only | "Reconnecting" |
| Offline | `navigator.onLine === false` | outline only | "Offline" |

- The change between states: the word swaps with `blurSwap` (200 ms). The mark's fill changes `background-color` over 150 ms `ease`.
- **No pulsing.** The mark is still when live. A constantly blinking dot is noise on a page open all day.
- A tooltip (kit `Tooltip`, plan 023's skip-delay) reads "Updated 2 s ago". It updates each second while open only.
- On the phone, show the square only, with `aria-label`.
- After a hidden tab becomes visible again (`poll.ts` already refetches at once), a fresh answer briefly glows the mark (`.v-glow`-style background on the word, 1200 ms).

Implementation: a `net` state module `src/lib/net.svelte.ts` with `lastOk: number`, `failing: boolean` and `online: boolean`. `live()` (`src/lib/live.svelte.ts`) and the layout's `count()` poll report into it: success sets `lastOk = Date.now()` and `failing = false`, failure sets `failing = true`. `online` comes from `window` `online`/`offline` events, attached with `<svelte:window ononline onoffline>` in the layout. A 1 s interval (only while mounted) re-derives "6 s since lastOk".

### B. Relative times for fresh items

In `ActivityRow`, when the item is less than 60 s old, show "Just now" instead of `hm(at)`. Under 60 min: "4 min ago". Otherwise the clock time as today. Fresh times re-render each 15 s through a shared clock (`now` in `net.svelte.ts`, ticking every 15 s). A change of the word swaps with `blurSwap`.

**Fixture mode** runs on the frozen demo clock (`CLOCK` in `src/lib/format.ts`), so relative words are wrong there. Only use relative times when `LIVE` is true.

### C. Open instantly: prefetch on intent

When a pointer rests on an Activity row for 80 ms (`pointerenter` + timer, cancelled on `pointerleave`), on `touchstart`, or on keyboard `focus`, start `api.activityItem(id)` and (for requests) `api.request(id)`, and put their promises' results into the live cache under the same keys the detail page uses (`item:${id}`, `request:${id}`; plan 003). The detail then opens with data already there: no skeleton, and the title morph (003) lands on real content.

- At most one prefetch per id per 10 s. Ignore errors (the page fetches again anyway).
- Add `prime(key: string, p: Promise<unknown>)` to the live cache module: it stores the value when the promise resolves.
- Do not prefetch on the phone's scroll-touch: only `touchstart` on the row itself, which does not fire for a scroll that starts elsewhere.

## Repo conventions to follow

- Tokens only. The band colours are `--valio-band-fg` and `--valio-band-muted`.
- Copy: "Live", "Reconnecting", "Offline", "Just now", "4 min ago", "Updated 2 s ago". No dashes.
- `poll()` (`src/lib/poll.ts`) is the only poller. Do not add a second network loop: the live mark reads what the existing polls report.

## Steps

1. Create `src/lib/net.svelte.ts` (`net` state, `reportOk()`, `reportFail()`, and the 15 s `now` clock started lazily by the first reader).
2. `src/lib/live.svelte.ts`: call `reportOk()` / `reportFail()` in the existing try/catch (only when `alive()`).
3. `src/routes/+layout.svelte`: same in `count()`. Render `<LiveMark />` (new `src/lib/v2/LiveMark.svelte`) in the band before `.kitchen` (desk and phone branches). Add `<svelte:window ononline={…} onoffline={…} />`.
4. `src/lib/v2/ActivityRow.svelte`: the relative time per B, and the prefetch handlers per C (`onpointerenter`, `onpointerleave`, `ontouchstart`, `onfocus`).
5. The live cache module (from 003): add `prime`.

## Boundaries

- No pulsing or blinking indicator.
- Do NOT prefetch in a loop or for every row on screen: only on intent for one row.
- If plan 003 is not done (no cache), skip C and do A and B.

## Verification

- **Mechanical**: `npm run check`, `npx playwright test`, `make e2e-live`.
- **Feel check**:
  - Live mode: the band says "Live". Stop the backend: within about 6 s the word swaps to "Reconnecting" and the mark empties. Start it again: back to "Live", with a brief glow.
  - DevTools Network "Offline": "Offline".
  - Run an agent scene: the new row says "Just now", and a minute later "1 min ago".
  - Hover a row for a moment, then click: the detail has its content on the first frame (Network panel: the request was made before the click).
  - Fixture build: rows still show clock times.
- **Done when**: the page always tells the truth about being live, and a considered click opens with no wait.
