# 021 — Replay a decision: watch Validio's reasoning step by step

- **Status**: DONE
- **Commit**: 61a5322
- **Severity**: LOW (high impact in a demo; the "explanation" tier)
- **Category**: Missed opportunities (explanation)
- **Depends on**: 001, 006, 011 (the proof chain look)
- **Estimated scope**: 1 file (`src/routes/activity/[id]/+page.svelte`) plus a small helper, ~160 lines

## Problem

A request detail already reads top to bottom as the story of a decision: what the agent asked, what Validio checked at Valio, which rule decided, the result, the proof (`src/routes/activity/[id]/+page.svelte:220-288`). On a projector, a presenter scrolls and points at each part while explaining. Nothing in the UI tells that story in order. It is all on screen at once.

## Target

A quiet **"Replay"** text button (lucide `Play` 14 px + "Replay") in the page head's actions, on request details only (not standing orders, and not while an approval is pending, because the owner should answer instead).

Pressing it plays the page as a sequence. Explanatory motion that the user triggers may take longer than UI motion:

| Step | Starts | What happens | Duration |
|:---|:---|:---|:---|
| 0 | 0 ms | every `.part` and the margin dims to `opacity: 0.32` (`transition: opacity 300ms var(--v-ease-out)`). A 2 px petrol progress line appears at the left edge of `.parts`, `transform: scaleY(0)` | 300 ms |
| 1 Asked | 300 ms | "What your agent asked" returns to full opacity. Its quote's left rule turns `--valio` | 300 ms, then a hold of 900 ms |
| 2 Checked | 1500 ms | "What Validio checked" lights up. Its check rows appear one by one (`opacity 0 → 1`, `translateY(4px) → 0`, 220 ms, gaps 120, 100, 90, 80 ms). The margin's "Valio asked for price and stock" lights with it. With the options table (plan 010 and Options), the chosen row gets `.v-glow` | ~900 ms, hold 900 ms |
| 3 Rule | 3300 ms | "Which rule decided" lights. The margin's limit scale (plan 010) replays its marker travel | 420 ms, hold 900 ms |
| 4 Result | 4620 ms | "Result" lights. If ordered, the check mark from plan 007 draws | 300 ms, hold 900 ms |
| 5 Proof | 5820 ms | the Proof fold opens (plan 011's chain draw plays) | 300 ms |
| end | ~6.4 s | everything returns to full opacity over 300 ms. The progress line fades | 300 ms |

Throughout, the progress line's `scaleY` follows the step (0.2, 0.4, 0.6, 0.8, 1) with `transition: transform 300ms var(--v-ease-in-out)`. Each step scrolls its part into view (`scrollIntoView({ block: "nearest", behavior: "smooth" })`), but only if it is off screen.

**Interruptible**: any click, wheel, key press, touch or a second Replay press stops the replay at once. Everything returns to full opacity (300 ms) and the Proof fold keeps whatever state it reached. The button label is "Stop" while playing. `Escape` also stops.

**Accessibility**: the sequence is visual only. A `role="status"` line announces "Replaying the decision" and "Replay finished". All content stays in the DOM and readable throughout. No content is hidden, only dimmed.

**Reduced motion**: no movement and no smooth scroll. Steps jump between states (the opacity still changes, 120 ms), and each hold is 1200 ms so it can be followed.

## Repo conventions to follow

- Sections have ids `h-asked`, `h-checks`, `h-rule`, `h-result` and `proof`. Use these to find them; do not add new testids except `replay`.
- Run the sequence with `async` steps and an `AbortController`. Each wait is `await sleep(ms, signal)` and each animation goes through classes plus CSS transitions. No rAF loops.

## Steps

1. Add `src/lib/replay.ts`: `sleep(ms, signal)` that rejects on abort, and `runSteps(steps: { at: () => void; hold: number }[], signal)`.
2. In the detail page: a `replaying` `$state` and a `step` `$state` (0 to 5). Class bindings: `.parts` gets `class:replaying`, each `.part` gets `class:lit={replaying && step >= n}` (a part stays lit once reached), and the margin rows likewise.
3. CSS:
   ```css
   .replaying .part, .replaying ~ .checked .ck { opacity: 0.32; transition: opacity 300ms var(--v-ease-out); }
   .replaying .part.lit, .replaying ~ .checked .ck.lit { opacity: 1; }
   .replay-line { position: absolute; left: -16px; top: 0; bottom: 0; width: 2px; background: var(--valio); transform-origin: top; transform: scaleY(var(--p)); transition: transform 300ms var(--v-ease-in-out), opacity 300ms var(--v-ease-out); }
   ```
   `--p` is set with `style:--p` on the line element itself (not a parent). `.parts` gets `position: relative`. On the phone the line sits at `left: -8px`.
4. Check rows' staggered reveal: a class `stagger` on `dl.checks` during step 2, with `nth-child` delays `0, 120, 220, 310, 390 ms`, and `@keyframes` from `opacity: 0; transform: translateY(4px)`, 220 ms `var(--v-ease-out)`, `both`.
5. Stop handler: `<svelte:window onkeydown onpointerdown onwheel ontouchstart>` active only while `replaying`. Each calls `controller.abort()` and resets.

## Boundaries

- Do NOT auto-play. Only on the button.
- Do NOT block interaction: the first input stops the replay and is then handled normally.
- Do NOT change any content or order of the page.

## Verification

- **Mechanical**: `npm run check`. A new spec `e2e/replay.spec.ts` (with reduced motion): open R-1, click `replay`, wait for "Replay finished" in the status, then check that the Proof is open and every `.part` has full opacity. Then start it again, press Escape, and check that it stopped.
- **Feel check** on a projector-size window: the story reads in about 6 seconds, the eye always knows where to look, and pressing anywhere stops it at once with no stuck dim.
- **Done when**: a presenter can say "watch" and the page explains the decision by itself.
