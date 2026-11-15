# Validio web app: the motion and interaction plans

Written on 15 Nov 2026 at commit `61a5322`. Built with the repo's frontend skills: `improve-animations` (audit and plan format), `find-animation-opportunities` (the gate), `choreograph` (timelines), `animate` (values and recipes), `emil-design-eng`, `svelte-core-bestpractices`. Each plan is self-contained: an agent with no other context can execute it. Run one with any agent, or with `improve-animations execute plans/NNN-….md`.

`src/frontend/UI-PLAN.md` is out of date and is **not** a constraint for these plans. The design to keep is the one that ships: `src/lib/tokens.css` and the current pages.

## What the audit found

The app today has almost no motion: hover colour shifts at 150 ms `ease`, a fold chevron that turns, and one 350 ms "flash" keyframe. The kit `Button` presses and the kit `Dialog` rises. Everything else teleports:

- Rows the agent adds through the 2-second poll appear in one frame. That is the product's main live moment, and it goes unnoticed.
- Every navigation, every state change (Agent, approval), every fold, form, error line and notice swaps instantly.
- Every visit starts on a skeleton, even straight after seeing the same data. Fast answers make it flicker.
- States disagree: some links fade their underline, others pop it. The focus ring sits outside full-width rows. Busy buttons only turn grey.
- The core rule (alone, waits, blocked) is only ever told in text.

There is nothing wrong to undo. All of this work is additive.

## Principles every plan follows

**The style stays.** Light by default, Valio petrol as the one accent, hairline rules rather than boxes, no shadows, small radii (3 to 6 px), Figtree, tabular figures. No new colours. Every value comes from `src/lib/tokens.css`. Motion is how the existing pieces behave, not new decoration.

**Motion has a job**: feedback, spatial consistency (where something came from or went), state indication, preventing a jarring change, or explanation. Delight only at first-time or rare moments (the door, finishing setup, the agent's first code, an approval landing).

**Frequency decides.** Things used tens of times a day (rows, filters, tabs) get near-instant, subtle motion. The palette and keyboard actions get none. Rare moments get more room.

**Values.**
- Curves: `--v-ease-out: cubic-bezier(0.23, 1, 0.32, 1)` for anything entering or leaving, `--v-ease-in-out: cubic-bezier(0.77, 0, 0.175, 1)` for movement on screen. Never `ease-in`. Colour changes use `ease`.
- Durations: press 140 ms, UI 200 ms, arrivals 260 ms, rare moments 420 ms, toasts 400 ms `ease`.
- Exits are shorter than enters.
- Only `transform`, `opacity`, `clip-path`, plus height for folds and arriving rows.
- One entrance per container. No stagger on lists people scan all day.

**Focus appears instantly. Hover only for real pointers. Reduced motion is gentler, not dead**: nothing travels, fades stay at 120 ms, idle loops stand still.

### What makes it look generated, and is therefore not used

These are the patterns that make an interface read as AI-made or template-made. None of the plans use them:

- gradients, mesh or aurora backgrounds, glow, neon outlines, glassmorphism and backdrop blur panels
- purple or blue-violet accents, any accent besides petrol
- sparkle or magic-wand icons, emoji in UI, "AI" badges
- typewriter text, shimmering or gradient text, text that "streams" in
- floating blobs, particles, confetti, 3D tilt cards, cursor-follow spotlights, parallax
- bouncy springs on everything, wobble, elastic overshoot
- big rounded cards with soft drop shadows, pill buttons
- counters that count up on every load, decorative skeleton shimmer
- stagger-everything page entrances, scroll-reveal on app pages

What is used instead: hairlines that draw, tints that fade, words that swap through a 2 px blur, a check that draws itself, things that grow out of what you pressed. That is the vocabulary of serious tools (banking, trading desks, Linear, Stripe's dashboard), not of demos.

## The plans

| # | Plan | What you will see | Severity | Status |
|:---|:---|:---|:---|:---|
| [001](001-motion-foundation.md) | Motion foundation | tokens, `$lib/motion.ts`, reduced motion, tests run reduced | HIGH | DONE |
| [002](002-press-and-hover-feedback.md) | Press and hover gate | every pressable answers the finger. No sticky hover on phones | HIGH | DONE |
| [018](018-interaction-states.md) | **Interaction states** | one matrix for hover, active, focus, busy, disabled, invalid, selected; inset focus on rows; spinners that wait 300 ms; focus moves to the page title | HIGH | DONE |
| [019](019-enter-and-exit-everywhere.md) | **Enter and exit everywhere** | every error line, hint, notice, conditional row and swapped word arrives and leaves smoothly; Start over crossfades | MEDIUM | DONE |
| [003](003-page-transitions-and-instant-revisits.md) | Page transitions, instant revisits | the clicked row's title travels into the detail heading. Back is instant | MEDIUM | DONE |
| [004](004-content-arrival-and-filter-swap.md) | Content arrival, filter swap | no skeleton flicker, one calm entrance, filters never blank the list | MEDIUM | DONE |
| [005](005-live-rows-arrive-and-leave.md) | Live rows | new orders slide in and glow petrol. Answered ones fold away | MEDIUM | DONE |
| [006](006-folds-that-open.md) | Folds | Proof, options and "Agent without MCP" open smoothly | MEDIUM | DONE |
| [007](007-the-approval-moment.md) | The approval moment | 6-cell code field, a shake on a wrong code, the answer lands as one wave | MEDIUM | DONE |
| [008](008-agent-connect-flow.md) | Agent connect | the page visibly listens, the code assembles itself, states hand over | MEDIUM | DONE |
| [009](009-home-figures-and-setup.md) | Home figures, setup | figures roll when they change, the week bar fills, setup completes with a moment | MEDIUM | DONE |
| [010](010-limit-scale-interactive.md) | Limit scale | the Rules as zones, draggable limits, where this order landed | MEDIUM | DONE |
| [020](020-live-status-and-instant-open.md) | **Live status, instant open** | a quiet Live / Reconnecting mark, "Just now" times, details prefetched on hover | MEDIUM | DONE |
| [012](012-live-notifications.md) | Live notifications | "Waiting for you" reaches you on any page, plus a count in the tab title | MEDIUM | DONE |
| [011](011-proof-chain-and-margin.md) | Proof chain | Proof draws as a linked chain, and margin links mark where they land | LOW | DONE |
| [021](021-decision-replay.md) | **Decision replay** | one button plays the request's story: asked, checked, rule, result, proof | LOW | DONE |
| [022](022-reading-aids.md) | **Reading aids** | a price ladder in options, sticky day heads, Find in Activity with highlights | LOW | DONE |
| [023](023-explain-in-place.md) | **Explain in place** | info popovers that grow from their icon, tooltips for cut-off text with skip-delay | LOW | DONE |
| [015](015-nav-indicators-and-phone.md) | Indicators, phone | underlines travel between tabs, and the status bar follows the theme | LOW | DONE |
| [016](016-settings-forms-and-theme-reveal.md) | Settings, theme reveal | forms open under their row, saves confirm, the theme reveals in a circle | LOW | DONE |
| [014](014-login-door.md) | The door | an entrance worth a first visit, and a live diagram of agent to Validio to outcome | LOW | DONE |
| [013](013-command-palette-and-keys.md) | Command palette, keys | ⌘K for every page and agent action, `g`/`j`/`k`, no animation | LOW | DONE |
| [017](017-motion-qa-pass.md) | QA pass | review, frame budget, reduced motion, phone, recording | HIGH | DONE |

The numbers are the order in which the plans were written. The table is in the recommended order. Bold rows were added in the second round.

## Order and dependencies

```
001 ─┬─ 002 ── 018 ─┬─ 022
     │              └─ 023
     ├─ 019
     ├─ 006 ─┬─ 011 ── 021
     │       └─ 007
     ├─ 003 ─┬─ 004 ── 005
     │       ├─ 020
     │       ├─ 015
     │       ├─ 016
     │       └─ 014
     ├─ 008, 009, 010, 012
     └─ 013 (independent)
all ── 017
```

1. **001, 002, 018, 019**: the base. After these, every element in the app behaves well on hover, press, focus, busy, appear and disappear.
2. **003, 004, 005, 006**: navigation, live data, folds.
3. **007, 008, 009, 010**: the four signature moments (approval, agent, home, rules).
4. **020, 012**: live feel and notifications.
5. **011, 021, 022, 023**: proof, replay, reading and explaining.
6. **015, 016, 014, 013**: polish, the first impression, keyboard.
7. **017** before merging.

For a demo deadline, the highest impact for the effort: **001, 002, 018, 019, 003, 005, 007, 008, 010, 021**.

## What shipped, and what did not (15 Nov 2026, branch `frontend-motion`)

All 23 plans are implemented. Left out on purpose:
- **Hold to reject** (007, optional step): not built; README decision 2 left it to the owner. Reject stays one press.
- **The hover price difference** in the options table (022 A, second paragraph): the sub line already says "Costs X more".
- **019 #9 and #11**: the kit `Row` takes its description as a plain string, so those swaps stay instant.
- **Settings forms leave without a fold** (016): two forms open in one moment would hold the same field ids.

Fixed on the way: a pressed kit Chip drew its label in its own fill colour (the kit's scoped rule beat app.css);
the press wash on activity rows took the faint time under 4.5:1, so the time turns muted on press.

## Decisions for you (the plans assume the recommendation)

1. **Rolling numbers.** Own `Ticker` (no dependency, test-safe) or `@number-flow/svelte` (per-digit roll, but renders in shadow DOM, so the text assertions need re-checking). *Recommendation: Ticker.* Plan 009.
2. **Hold to reject.** Reject is irreversible and needs no code. A 2 s hold would prevent slips but slows the demo. *Recommendation: yes for real kitchens, skip if demo speed matters more.* Plan 007, optional step.
3. **Tab title count** "(1) Validio" while an order waits. *Recommendation: yes.* Plan 012.
4. **Toast for orders placed alone.** Useful live, noisy when Steady orders renew several lines. *Recommendation: no.* Toast only for waiting, the agent calling, and blocked. Plan 012.
5. **Replay button visibility.** Always on request details, or only on demo kitchens. *Recommendation: always.* It also helps a real owner understand a decision. Plan 021.

## Considered and rejected

- **Staggering Activity rows on every visit**: a list scanned many times a day. A stagger slows every use after the first.
- **Hover lift, scale or shadow on rows and cards**: tens per day, and out of character with the flat hairline style.
- **Scroll reveal on app pages**: re-animating content you are reading fights the reader.
- **Animated money inside rows, the options table, the price ladder**: data being read and compared. Only Home's headline figures roll, and only when they change.
- **A pulsing "live" dot**: noise on a page open all day. The Live mark (020) is still when all is well and changes only when something is wrong.
- **Confetti, glow, particles on success**: generated-looking. The approval landing uses a drawn check and a crossfade.
- **Open and close animation for the command palette, animated focus rings**: keyboard paths stay instant.
- **Parallax or mouse-tracking on the login panel**: decoration with no job.

## Before executing any plan

- `npm run kit && npm ci` in `src/frontend` (the Arlen kit is fetched, never edited).
- **Note:** on 15 Nov, `npm run check` failed in this checkout with `ETIMEDOUT` while reading a module, not with a type error. `~/Desktop` is synced to iCloud Drive (`~/Library/Mobile Documents/com~apple~CloudDocs/Desktop` links to it), so files can be evicted from disk. Keep the folder downloaded (Finder, "Keep Downloaded") or move the repo out of iCloud before running checks.
- Every `.svelte` change goes through the `svelte-code-writer` skill's autofixer (AGENTS.md).
