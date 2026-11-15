# 011 — Proof reads as a chain; the margin's links take you somewhere visibly

- **Status**: DONE
- **Commit**: 61a5322
- **Severity**: LOW
- **Category**: Missed opportunities (explanation), Choreography
- **Depends on**: 001, 006
- **Estimated scope**: 1 file (`src/routes/activity/[id]/+page.svelte`), ~70 lines

## Problem

"Sealed" is Validio's trust claim: every entry carries the hash of the one before. In the UI, Proof is a flat list of time, actor, text and hash (`:275-286`). Nothing makes the *chain* visible. When the fold opens, all entries appear at once.

```svelte
<!-- src/routes/activity/[id]/+page.svelte:275-286 — current -->
<ol class="pes">
  {#each d.proof as p (p.hash)}
    <li class="pe" data-raw>
      <span class="pe-time num">{secs(p.at)}</span>
      <span class="pe-actor smallcaps">{p.actor}</span>
      <span class="pe-main">
        <span class="pe-text">{p.text}</span>
        <span class="pe-hash mono">{p.hash}</span>
      </span>
    </li>
  {/each}
</ol>
```

The margin links "See the proof" and "Show this product" jump the page and leave no mark at their target.

## Target

**A. The chain line.** A 1 px vertical line `var(--v-line-strong)` runs through the left of the entries, with a 7 px node per entry (`border: 1.5px solid var(--valio); background: var(--v-surface); border-radius: var(--radius-chip)`). The line belongs to the `<ol>` (`::before`). On opening, it draws from the top: `transform: scaleY(0 → 1)`, `transform-origin: top`, 300 ms `--v-ease-out`. Opening Proof is occasional, and the motion explains "each one follows from the last".

**B. Entries on opening.** A short overlap so the chain reads as building up, capped so the group finishes under 300 ms:

| Entry | Delay | Motion |
|:---|:---|:---|
| 1 | 0 ms | `opacity 0 → 1`, `translateY(4px) → 0`, 220 ms `--v-ease-out` |
| 2 | 30 ms | same |
| 3 | 55 ms | same |
| 4 | 75 ms | same |
| 5 and later | 90 ms | same, all together |

These are CSS animations under `details.proof[open]`. They replay each time the fold opens, which is fine: it is occasional and short. No stagger on close: the fold collapses as one (plan 006).

**C. Hash.** Keep the full hash (it is proof). Click it to copy, with a 150 ms `blurSwap` to "Copied" and back after 1.6 s. A `title` holds the full hash for long ones on the phone.

**D. Landing marks.** "See the proof" scrolls (smooth, or `auto` under reduced motion), opens the fold, and puts `.v-glow` (plan 001) on the summary. "Show this product" already uses `.v-glow` after plan 001. Make its `scrollIntoView` honour reduced motion too.

Reduced motion: no line draw (the line is simply there), entries fade 120 ms with no delays.

**E. One entrance per container.** Plan 006 makes every fold grow its height. For Proof, the chain building up *is* the entrance, and a growing fold with a stagger inside it is two layers of entrance. Proof therefore opens without the height transition (`details.fold.proof::details-content { transition: none; }`), and the line and entries carry the motion.

## Repo conventions to follow

- `[data-raw]` marks text the slop check (`e2e/helpers.ts:slop`) skips. Keep it on `.pe`.
- The fold is `details.fold.proof` with summary `#proof-toggle`. `e2e/activity-detail.spec.ts:20-22` expects `.pe` hidden before the click and 3 entries after it.

## Steps

1. In `<style>` add:

   ```css
   .pes { position: relative; padding-left: 20px; }
   .pes::before { content: ""; position: absolute; left: 3px; top: 18px; bottom: 18px; width: 1px; background: var(--v-line-strong); transform-origin: top; }
   .pe { position: relative; }
   .pe::before { content: ""; position: absolute; left: -20px; top: 19px; width: 7px; height: 7px; border: 1.5px solid var(--valio); background: var(--v-surface); border-radius: var(--radius-chip); }
   details.proof[open] .pes::before { animation: v-chain 300ms var(--v-ease-out) both; }
   details.proof[open] .pe { animation: v-pe 220ms var(--v-ease-out) both; animation-delay: 90ms; }
   details.proof[open] .pe:nth-child(1) { animation-delay: 0ms; }
   details.proof[open] .pe:nth-child(2) { animation-delay: 30ms; }
   details.proof[open] .pe:nth-child(3) { animation-delay: 55ms; }
   details.proof[open] .pe:nth-child(4) { animation-delay: 75ms; }
   @keyframes v-chain { from { transform: scaleY(0); } }
   @keyframes v-pe { from { opacity: 0; transform: translateY(4px); } }
   @media (prefers-reduced-motion: reduce) {
     details.proof[open] .pes::before { animation: none; }
     details.proof[open] .pe { animation: v-pe-fade 120ms linear both; animation-delay: 0ms; }
     @keyframes v-pe-fade { from { opacity: 0; } }
   }
   ```

   Align `top` of the node with the first text line of `.pe`. Check against the real padding (`.pe` padding is 12 to 14 px), and adjust `top` so the node centre sits on the time's baseline row.
2. In `src/app.css`, inside plan 006's `@supports (interpolate-size: allow-keywords)` block, add `details.fold.proof::details-content { transition: none; }`.
3. Hash copy: replace `<span class="pe-hash mono">{p.hash}</span>` with a `<button type="button" class="pe-hash mono" title={p.hash} onclick={() => copyHash(p.hash)}>`, showing `{#key copiedHash === p.hash}<span in:blurSwap={{ duration: 150 }}>{copiedHash === p.hash ? "Copied" : p.hash}</span>{/key}`. Reset the button's own styles (`border: 0; background: none; padding: 0; font: inherit; color: inherit; text-align: left; cursor: pointer`). Add `aria-label="Copy hash"`.
4. `toProof()`: after `scrollIntoView`, add `document.querySelector("#proof > summary")?.classList.add("v-glow")` and remove it after 1600 ms.
5. `src/routes/activity/[id]/Options.svelte` `show()`: `row?.scrollIntoView({ block: "center", behavior: reduced() ? "auto" : "smooth" })`.

## Boundaries

- Do NOT shorten or hide the hash by default.
- Do NOT claim a verification the browser does not do. No "Verified ✓" animation: the client does not recompute hashes.
- If an excerpt does not match, STOP and report.

## Verification

- **Mechanical**: `npm run check`. `npx playwright test e2e/activity-detail.spec.ts`. Run the slop check through the same spec.
- **Feel check**: open Proof on R-1. The line draws down while the entries fall into place just behind it, finished in about 0.3 s. Close and open it again: the same, never stacked. "See the proof" scrolls, opens and briefly tints the summary. Click a hash: "Copied" fades in and back.
- **Done when**: Proof visibly reads as a linked chain, and both margin links leave a mark where they land.
