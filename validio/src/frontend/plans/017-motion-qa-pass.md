# 017 — The motion QA pass: review, measure, record

- **Status**: DONE
- **Commit**: 61a5322
- **Severity**: HIGH (gate before merge)
- **Category**: Performance, Accessibility, Cohesion
- **Depends on**: every plan that was executed
- **Estimated scope**: no feature code; fixes only where a check fails

## Problem

Sixteen plans each add motion in their own corner. Each can pass its own feel check and still clash with the others: two entrances on one container, a curve typed by hand instead of a token, a transition left on a keyboard path, a dropped frame on the 2-second poll. This pass looks at the whole.

## Steps

1. **Static sweep** (from `src/frontend`). Each command must print nothing, or only lines you can justify in the PR:
   ```sh
   grep -rn "transition: all" src
   grep -rn "ease-in[^-]" src             # never ease-in on UI
   grep -rn "scale(0)" src                # never from nothing (the .wk-fill @starting-style is the one documented exception)
   grep -rnE "cubic-bezier\(" src | grep -v tokens.css | grep -v "lib/motion.ts" | grep -v theme.svelte.ts
   grep -rnE "animation:|transition:" src --include=*.svelte | grep -vE "var\(--v-(dur|ease)|var\(--duration|steps\(1\)|linear|none"
   ```
   The last two catch hand-typed timings. Each hit is replaced with a token, or justified (the toast's `ease`, the spinner's `linear`).
2. **Run the skill `review-animations`** on the full diff since 61a5322, against `.claude/skills/review-animations/STANDARDS.md`. Fix every blocking finding.
3. **Keyboard paths animate nothing**: open the palette, move focus with `j`/`k`, use the `1` to `5` filters, and Tab through Rules edit. Use the DevTools Animations panel with recording on: no animation is recorded for any of them.
4. **Frame budget** (skill `animation-performance`): in the Chrome Performance panel with 4× CPU throttling, record (a) Home with the agent adding a row (plan 005), (b) a list-to-detail navigation (003), (c) dragging a limit handle (010), (d) a theme reveal (016). No long task over 50 ms during the motion, and no layout shift outside the collapsing row or fold.
5. **Reduced motion** across the app (Rendering panel, emulate `prefers-reduced-motion: reduce`): nothing travels, the idle loops stand still, and fades are about 120 ms. Then run `make a11y` (it uses reduced motion through plan 001) and the axe check with motion on: run `npx playwright test -c a11y/a11y.config.ts` once with `reducedMotion` removed locally, to catch contrast during fades.
6. **Phone**: on a real iPhone and Android device, run the main path: Try the demo kitchen, Home, Activity, a waiting item, Approve with the code, Agent, Rules edit (drag), Settings theme. Check: no sticky hovers, no tap flash, the toasts swipe, the handles are grabbable, and the status bar matches the theme.
7. **Recording**: `node scripts/record-video.mjs` (the demo video runs with motion). Watch it at 0.25× and look for double entrances, flicker on poll and any frame where two states overlap.
8. **Next-day look**: re-watch the recording a day later with fresh eyes (Emil's rule). Cut anything that feels slow on the third viewing.
9. **Docs**: in `docs/TESTING.md`, add one paragraph: tests run with `reducedMotion: "reduce"`, and why. In `plans/README.md`, confirm "Principles" still matches what shipped.
10. Update `plans/README.md`: set each executed plan's status to DONE.

## Boundaries

- This pass only fixes. It does not add motion.
- If a fix would change a plan's target values, change the plan file first, then the code.

## Verification

- **Done when**: steps 1 to 9 pass, the `review-animations` verdict is "ship", and `make test` is green.
