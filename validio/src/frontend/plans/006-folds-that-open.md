# 006 — Folds open and close instead of snapping

- **Status**: DONE
- **Commit**: 61a5322
- **Severity**: MEDIUM
- **Category**: Missed opportunities (state indication)
- **Depends on**: 001
- **Estimated scope**: 1 file (`src/app.css`), ~30 lines

## Problem

Every "fold" in the app is a native `<details class="fold">`: Proof and "What Validio confirmed" on a request, the turned-down options, and "Agent without MCP". It snaps open, and the content below jumps by the full height in one frame. Only the chevron moves, and it uses the weak built-in `ease`:

```css
/* src/app.css:698-704 — current */
details.fold > summary .chev {
  width: 14px;
  height: 14px;
  transition: transform var(--duration-fast) ease;
}
details.fold[open] > summary .chev {
  transform: rotate(90deg);
}
```

## Target

Progressive enhancement with the `::details-content` pseudo-element and `interpolate-size` (Chrome/Edge 131+; elsewhere the fold keeps snapping exactly as today). Height plus opacity, 200 ms, `--v-ease-out`. The chevron uses the same duration and curve, so the fold and its chevron read as one object.

```css
details.fold > summary .chev {
  transition: transform var(--v-dur-ui) var(--v-ease-out);
}
@supports (interpolate-size: allow-keywords) {
  details.fold {
    interpolate-size: allow-keywords;
  }
  details.fold::details-content {
    block-size: 0;
    opacity: 0;
    overflow: clip;
    transition:
      block-size var(--v-dur-ui) var(--v-ease-out),
      opacity var(--v-dur-ui) var(--v-ease-out),
      content-visibility var(--v-dur-ui) allow-discrete;
  }
  details.fold[open]::details-content {
    block-size: auto;
    opacity: 1;
  }
}
```

Being transitions, these retarget when someone clicks a fold twice quickly. They never restart from zero.

## Repo conventions to follow

- There is exactly one fold style, "the one fold" in `src/app.css:679-720`. Every fold uses `details.fold` plus `.chev`. Change it there, not per component.

## Steps

1. In `src/app.css`, replace the `transition` line of `details.fold > summary .chev` with `transition: transform var(--v-dur-ui) var(--v-ease-out);`.
2. Directly after the `details.fold .fold-body p + p` rule, add the `@supports` block above.
3. Check the proof fold (`src/routes/activity/[id]/+page.svelte:269`, `details.fold.proof`). It is opened programmatically by "See the proof" (`proofOpen = true`, then `scrollIntoView`). With the transition, the scroll lands before the fold has its full height. Change `toProof` so the scroll waits for the open transition:

   ```ts
   async function toProof(e: MouseEvent) {
     e.preventDefault();
     proofOpen = true;
     await tick();
     const el = document.getElementById("proof");
     el?.scrollIntoView({ block: "start", behavior: reduced() ? "auto" : "smooth" });
   }
   ```

   Import `reduced` from `$lib/motion`. `block: "start"` on the `<details>` itself does not depend on the content height, so no wait is needed.

## Boundaries

- Do NOT replace `<details>` with a JS collapsible. Native details keeps find-in-page and keyboard behaviour.
- Do NOT animate summary text or the fold body's children separately. One container, one motion.
- No changes to kit `Collapsible` (it already animates).

## Verification

- **Mechanical**: `npm run check`. `npx playwright test e2e/activity-detail.spec.ts` checks that `#proof .pe` is hidden before the toggle and that 3 entries show after it.
- **Feel check** (Chrome):
  - On a request, open and close Proof. The content grows and fades in 200 ms, and the chevron turns in the same beat. At 10% playback both end together.
  - Double-click the summary quickly: the fold reverses from where it is, with no jump.
  - Ctrl+F for a word inside a closed fold: the browser opens it and finds it.
  - Firefox: folds snap as before, with no errors.
  - Reduced motion: the fold opens over 120 ms (`--v-dur-ui` becomes 120 ms). The height still interpolates in that short time. That is acceptable: no element travels, and the content below moves only as far as the fold grows.
- **Done when**: every `details.fold` opens and closes smoothly in Chromium and nothing changes elsewhere.
