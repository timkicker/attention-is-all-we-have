# 009 — Home: figures that tick when they change, a week bar that fills, a checklist that completes itself

- **Status**: DONE
- **Commit**: 61a5322
- **Severity**: MEDIUM
- **Category**: Missed opportunities (state indication, delight at a first-time moment), Performance
- **Depends on**: 001
- **Estimated scope**: 3 files (1 new component), ~150 lines

## Problem

Home is the page the owner keeps open. It polls every 2 s.

1. **Figures change silently.** "Spent this week" and "waiting for you" (`src/routes/+page.svelte:120-131`) swap their text in one frame when the agent orders:
   ```svelte
   <span class="f-num num">{nb(money(h.week.usedCents))}</span>
   …
   <span class="f-num num" class:wait={h.needsYou.length > 0}>{h.needsYou.length}</span>
   ```
2. **The week bar** is the kit `Progress`. It animates `width`, a layout property, with the kit's 150 ms (`vendor/…/progress/progress.svelte:53`). That is too fast to notice and costs a reflow each frame.
3. **The checklist** (`:101-118`) shows "Done" text when a step completes through polling (the agent connects in another tab). The number stays a number, and "1 of 3" swaps without a beat. When the third step completes, the whole page switches from the checklist to the dashboard in one frame. This is the kitchen's first real success, and the product says nothing.

## Target

**A. `Ticker.svelte`** (new, `src/lib/v2/Ticker.svelte`): a value that, when it changes, slides the new text in from the direction of change while the old one leaves the opposite way. At rest the DOM holds exactly one text node, so `toContainText` and `innerText` stay correct.

- New text: `in:` `opacity 0 → 1`, `translateY(±8px) → 0`, `blur(2px) → 0`, 260 ms `easeOut`. Up when the value grew, down when it shrank.
- Old text: `out:`, positioned `absolute` at its spot, `opacity 1 → 0`, `translateY(0 → ∓8px)`, 160 ms `easeOut`. Exits are shorter.
- The wrapper is `display: inline-grid` so old and new overlap in one cell, `overflow: clip` vertically only (`overflow-x: visible; overflow-y: clip`). `font-variant-numeric: tabular-nums` keeps the width steady.
- Reduced motion: a 120 ms crossfade, no travel, no blur.
- No transition on first render (local transitions).

**B. Week bar**: replace kit `Progress` with an own `.wk` track in the page. Same `role="progressbar"`, `aria-valuenow/min/max` and `aria-labelledby="week-label"`. The fill is a full-width element with `transform: scaleX(p)`, `transform-origin: left`, and `transition: transform var(--v-dur-moment) var(--v-ease-out)`. The first appearance grows from `scaleX(0)` through `@starting-style`. A fill at zero is the value zero, so this is not the "never scale(0)" case: the bar is data, not an appearing object.

**C. Checklist completes itself**:

| Moment | Element | Motion |
|:---|:---|:---|
| A step turns done while watching | `.st-n` number | replaced by a check drawn in `--v-ok`: SVG `M20 6 9 17l-5-5`, `pathLength="1"`, `stroke-dashoffset 1 → 0`, 300 ms `--v-ease-out`, 60 ms delay. The number leaves with `out:blurSwap` (120 ms) |
| | "Done" detail line | `{#key s.done}` + `in:blurSwap` |
| | "n of 3" | Ticker |
| All three done while watching (rare, first-time) | a one-line note above the figures, "Your kitchen is set up", with a check | `in:rise={{ y: 10, duration: 420 }}` (`--v-dur-moment`) |
| | figures, with role and delay | week figure (lead): `in:rise={{ y: 10, duration: 420, delay: 60 }}`; waiting (support): `{ y: 6, duration: 360, delay: 130 }`; alone (decoration): fade only, `{ y: 0, duration: 300, delay: 180 }`. Gaps shrink (70, then 50) so it reads as a wave |
| | Needs you and Latest sections | appear together with the waiting figure, fade only, no stagger inside |

"Watching" means the transition from `first === true` to `false` happened while the page was mounted. Track it with a plain `let wasFirst: boolean | null = null` and an `$effect`: if `wasFirst === true && !first`, set `celebrate = true`. Only `celebrate` enables the delays and the note. Opening Home later shows the dashboard with no motion.

## Repo conventions to follow

- Home's figure styles: `.f-num`, `.f-cap`, `.fig` in `src/routes/+page.svelte` `<style>`.
- Money text always comes from `money()` / `nb()` (`$lib/v2`). The Ticker takes the **formatted string** plus a numeric `value` for the direction. It never formats.
- Keep the testids: `home-week`, `home-status`, `setup-count`, `section-setup`, `step-*-go`.

## Steps

1. **Create `src/lib/v2/Ticker.svelte`**:

   ```svelte
   <script lang="ts">
     /// A figure that, when it changes, rolls the new text in from the side it moved to.
     import { easeOut, reduced } from "$lib/motion";
     let { text, value }: { text: string; value: number } = $props();
     let dir = $state(1);
     let last = value;
     $effect.pre(() => {
       if (value !== last) dir = value > last ? 1 : -1;
       last = value;
     });
     const enter = (_n: Element) =>
       reduced()
         ? { duration: 120, css: (t: number) => `opacity:${t}` }
         : { duration: 260, easing: easeOut, css: (t: number, u: number) => `opacity:${t};transform:translateY(${u * 8 * dir}px);filter:blur(${u * 2}px)` };
     const leave = (_n: Element) =>
       reduced()
         ? { duration: 120, css: (t: number) => `opacity:${t}` }
         : { duration: 160, easing: easeOut, css: (t: number, u: number) => `position:absolute;opacity:${t};transform:translateY(${-u * 8 * dir}px)` };
   </script>

   <span class="tk">{#key text}<span class="tk-v" in:enter out:leave>{text}</span>{/key}</span>

   <style>
     .tk { display: inline-grid; position: relative; overflow-x: visible; overflow-y: clip; vertical-align: bottom; }
     .tk-v { grid-area: 1 / 1; white-space: nowrap; }
   </style>
   ```

   Export it from `src/lib/v2/index.ts`.
2. **`src/routes/+page.svelte`**:
   - `<span class="f-num num"><Ticker text={nb(money(h.week.usedCents))} value={h.week.usedCents} /></span>`. Same for `h.needsYou.length`, and for `{doneCount} of 3` (text `` `${doneCount} of 3` ``, value `doneCount`).
   - Replace `<Progress value={weekPct} labelledby="week-label" />` with:
     ```svelte
     <div class="wk" role="progressbar" aria-labelledby="week-label" aria-valuenow={weekPct} aria-valuemin={0} aria-valuemax={100}>
       <span class="wk-fill" style:transform="scaleX({Math.min(100, weekPct) / 100})"></span>
     </div>
     ```
     ```css
     .wk { position: relative; width: 100%; min-width: 200px; height: 4px; margin-top: 8px; background: var(--v-line); overflow: hidden; }
     .wk-fill { position: absolute; inset: 0; background: var(--valio); transform-origin: left center; transition: transform var(--v-dur-moment) var(--v-ease-out); }
     @starting-style { .wk-fill { transform: scaleX(0); } }
     ```
     Delete the now-unused `.fig :global(.progress)` and `.fig :global(.progress-fill)` rules, and the `Progress` import.
   - Checklist number: `{#if s.done}<svg class="st-check" …><path d="M20 6 9 17l-5-5" pathLength="1"/></svg><span class="sr-only">Done</span>{:else}<span out:blurSwap={{ duration: 120 }}>{n + 1}</span>{/if}` inside `.st-n`. The check's draw animation goes under a `.just` class set when that step flipped while mounted (the same pattern as `celebrate`, keyed per step id in a plain `Set<string>`).
   - Celebration: `celebrate` as described. When true, render `<p class="v-set" in:rise={{ y: 10, duration: 420 }}>` with a check and "Your kitchen is set up" before `.figs`. Add the delayed `in:rise` per figure only when `celebrate` is true, e.g. `in:rise={celebrate ? { y: 10, duration: 420, delay: 60 } : { duration: 0 }}`.

## Boundaries

- Do NOT animate figures on first render or on revisit.
- Do NOT add confetti, glow, emoji or a modal for the celebration.
- Do NOT use `@number-flow/svelte` unless README decision 1 chose it. If chosen: `<NumberFlow value={cents / 100} locales="en-US" format={{ minimumFractionDigits: 2, maximumFractionDigits: 2 }} suffix={" €"} transformTiming={{ duration: 400, easing: "cubic-bezier(0.23, 1, 0.32, 1)" }} spinTiming={{ duration: 400, easing: "cubic-bezier(0.23, 1, 0.32, 1)" }} opacityTiming={{ duration: 200, easing: "ease-out" }} />`, then verify `home.spec.ts` text assertions, because NumberFlow renders in shadow DOM.
- If an excerpt does not match, STOP and report.

## Verification

- **Mechanical**: `npm run check`. `npx playwright test e2e/home.spec.ts` (asserts `home-week` contains "1,190.10" and "8,000.00", and `setup-count` "0 of 3"). `make a11y`: the progressbar keeps its name.
- **Feel check**:
  - Live mode, Home open, run `make agent SCENE=1`: "spent this week" rolls up, and the bar extends smoothly over about 0.4 s.
  - Approve something elsewhere: "waiting for you" rolls down (the opposite direction).
  - New kitchen (sign up) with Home open: connect the agent in a second tab. Step 2's number becomes a drawn check, and "1 of 3" rolls to "2 of 3". After the first order, the note and the figures come in as a short wave. Reload: everything is still.
  - Reduced motion: crossfades only, the bar jumps.
- **Done when**: no Home figure changes silently, and the first setup completion gets its one moment.
