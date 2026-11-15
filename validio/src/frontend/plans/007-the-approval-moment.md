# 007 — The approval moment: a code field that feels physical, a wrong code that shakes, an answer that lands

- **Status**: DONE
- **Commit**: 61a5322
- **Severity**: MEDIUM (the product's signature interaction)
- **Category**: Missed opportunities (feedback, state indication), Choreography
- **Depends on**: 001, 006. 009 (Ticker) is optional for the proof count.
- **Estimated scope**: 3 files, ~200 lines

## Problem

Approving a waiting order is what Validio exists for: the agent stops and the owner decides. Today every step teleports:

```svelte
<!-- src/routes/activity/[id]/+page.svelte:195-216 — current (abridged) -->
{#if !asking}
  <div class="v-buttons">
    <Button id="approve" … onclick={() => (asking = true)}>Approve</Button>
    <Button id="reject" … variant="outline" … onclick={reject}>Reject</Button>
  </div>
{/if}
{#if problem && !asking}<p class="ask-problem" role="alert">{problem}</p>{/if}
{#if asking}
  <VCode bind:value={code} error={problem} {busy} submitLabel="Approve" onsubmit={confirm} oncancel={…} />
{/if}
```

- The code field (`src/lib/v/VCode.svelte`) is one plain text input. A wrong code only changes the help line's text.
- After a successful approve, `bump()` refetches. The `.ask` notice vanishes, the lede's status word changes from "Waiting for you" to "Approved by you", and the Result section changes from "Not ordered yet" to "Placed with Valio", all in one frame. A presenter has to point at the screen to show what happened.

## Target

### A. Code field (`VCode.svelte`, also used by Rules edit)

Six visual cells over **one real `<input>`**. The input keeps `id="approve-code"` and `data-testid="code-input"`, stays focusable and fillable by Playwright, and is laid over the cells with transparent text. The cells are `aria-hidden`.

- Cell: `width: 40px; height: 48px` on desk, `44px × 52px` at ≤760 px. `border: 1px solid var(--v-line-strong); border-radius: var(--radius-input)`. Digit at `font-size: 22px`, `font-variant-numeric: tabular-nums`, `font-family: var(--font-mono)`.
- Active cell (next to fill, while focused): `border-color: var(--valio)`, `box-shadow: none`. A 2 px caret bar `background: var(--valio)` blinks with `animation: v-caret 1s steps(1) infinite` (a native caret blinks too; the kit's reduced-motion block does not cover it, so stop it under reduced motion).
- A digit appearing: `animation: v-digit 120ms var(--v-ease-out)` from `opacity: 0; transform: scale(0.9)`. Feedback; at most 6 times per approval.
- Wrong code (`error` set): the cell row shakes once. Keyframes `0%,100% {transform: translateX(0)} 20% {-6px} 40% {6px} 60% {-4px} 80% {4px}`, 320 ms `var(--v-ease-out)`, and all cell borders turn `var(--v-bad)`. It must replay on every new error: toggle the class off, force a reflow (`void el.offsetWidth`), then toggle it on. Reduced motion: no shake, the border colour only.

### B. Approve to code field

`VCode` enters with `in:rise={{ y: 6, duration: 200 }}`. The Approve and Reject buttons leave instantly, with no out transition. Cancel brings the buttons back with `in:rise`, and focus returns to `#approve` as today.

### C. The answer lands (choreography timeline)

Starts when `said` is set (the approve or reject call returned) **or** when polling turns `d.approval` from set to null while the page is open (someone approved on another device). Same timeline either way:

| Element | Role | Starts | Duration | Motion | Relationship |
|:---|:---|:---|:---|:---|:---|
| Status word in the lede (`[data-testid=detail-status]`) | Lead | 0 ms | 200 ms | `{#key pill.label}` with `in:blurSwap={{ y: 4 }}`: the new word comes in with a 2 px blur clearing | — |
| `.ask` notice | Support | 0 ms | 220 ms | `out:collapse={{ duration: 220 }}` (height and opacity) | Together with the lead |
| Result section content (`dl.checks` inside `#h-result`) | Support | 80 ms | 260 ms | `in:rise={{ y: 6, delay: 80 }}` | Overlaps the lead |
| Check mark before "Placed with Valio" | Decoration | 160 ms | 300 ms | SVG path `M20 6 9 17l-5-5` with `pathLength="1"`, `stroke-dasharray: 1; stroke-dashoffset: 1 to 0`, `var(--v-ease-out)`, `animation-fill-mode: both` | Lands as the row settles |
| Proof summary count ("3 entries, sealed") | Decoration | 0 ms | 200 ms | Ticker from plan 009 if present, otherwise no motion | Together |

Total about 460 ms, inside the rare-moment budget. Everything is clickable from frame one. Reject plays the same timeline without the check mark (the result stays "Nothing ordered").

These are local Svelte transitions, so they play only when the blocks flip while the page is open, not when you open an already-approved request.

## Repo conventions to follow

- `$lib/motion`: `rise`, `collapse`, `blurSwap` (plan 001).
- The status word uses `tone-{tone}-text` classes from `src/app.css:460-470`. Keep them.
- Keep the ids and testids: `approve`, `reject`, `approval`, `detail-status`, `detail-total`, `result-order`, `result-none`, `code-input`, `code-submit`.
- `check-tokens.mjs`: no colour or radius literal in `.svelte` style blocks.

## Steps

1. **`src/lib/v/VCode.svelte`**: restructure the `.line` so the input sits in a `.cells` box:

   ```svelte
   <div class="cells" class:shake bind:this={cellsEl}>
     {#each Array(6) as _, i (i)}
       <span class="cell" class:active={focused && i === Math.min(value.length, 5)} aria-hidden="true">
         {#if value[i]}<span class="digit">{value[i]}</span>{:else if focused && i === value.length}<span class="caret"></span>{/if}
       </span>
     {/each}
     <Input id="approve-code" bind:value … class="code-overlay mono" onfocus={() => (focused = true)} onblur={() => (focused = false)} />
   </div>
   ```

   Keep `inputmode`, `autocomplete="one-time-code"`, `maxlength={6}`, `aria-invalid` and `aria-describedby`. Strip non-digits on input: `oninput={(e) => (value = e.currentTarget.value.replace(/\D/g, "").slice(0, 6))}`. `.code-overlay`: `position: absolute; inset: 0; opacity: 0.01; color: transparent; caret-color: transparent; letter-spacing: 40px` (selection then follows the cells roughly). Use `opacity: 0.01`, not `0`, so it counts as visible for every engine.

   Shake: an `$effect` on `error`. When it becomes non-empty and `!reduced()`, remove `shake`, read `cellsEl.offsetWidth`, then add `shake` again (a `shake` `$state` toggled false, `await tick()`, then true).

   Styles: the values in section A, with keyframes `v-caret`, `v-digit` and `v-shake`, and `@media (prefers-reduced-motion: reduce) { .caret { animation: none; } .cells.shake { animation: none; } }`.
2. **`src/routes/activity/[id]/+page.svelte`**:
   - Wrap `<VCode …/>` in `<div in:rise={{ y: 6, duration: 200 }}>`, and `.v-buttons` in `<div in:rise={{ y: 6, duration: 200 }}>`.
   - Change `{#if d.approval}<div class="ask notice" …>` to carry `out:collapse={{ duration: 220 }}`.
   - In the lede snippet, wrap the status word:
     ```svelte
     {#key pill.label}<span class="word tone-{pill.tone}-text" data-testid="detail-status" in:blurSwap={{ y: 4 }}>{pill.label}</span>{/key}
     ```
   - On the Result `dl.checks` add `in:rise={{ y: 6, delay: 80 }}`. In the `result-order` row, before the text, add:
     ```svelte
     <svg class="done-mark" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="M20 6 9 17l-5-5" pathLength="1" /></svg>
     ```
     ```css
     .done-mark path { fill: none; stroke: var(--v-ok); stroke-width: 2.25; stroke-linecap: round; stroke-linejoin: round; stroke-dasharray: 1; stroke-dashoffset: 0; }
     .ck-val.ok .done-mark path { animation: v-draw 300ms var(--v-ease-out) 160ms both; }
     @keyframes v-draw { from { stroke-dashoffset: 1; } }
     @media (prefers-reduced-motion: reduce) { .ck-val.ok .done-mark path { animation: none; } }
     ```
     A CSS animation plays on every mount, including a fresh visit to an already-ordered request. Gate it with a class `just` that is set only when the result appeared while the page was open: keep a plain variable `let hadResult: boolean | null = null`. In an `$effect` on `d`: if `hadResult === false && d.result`, set `justDone = true`. Then set `hadResult = !!d.result`. Apply `class:just={justDone}` and target `.ck-val.ok.just .done-mark path`.
   - `role="status"` already announces `said`. Leave it.
3. **`src/routes/rules/edit/+page.svelte`** uses `VCode` with `focus={false}` and no submit label. Check that the cells render at the end of the form and that `rules.spec.ts` (`code-input` `.fill`) still passes.

## Optional (decision for the owner, see README): hold to reject

Reject is irreversible and needs no code. If the owner wants it, use the hold-to-confirm recipe: an overlay inside the Reject button with `clip-path: inset(0 100% 0 0)` going to `inset(0 0 0 0)` over `2s linear` while pressed, snapping back over `200ms var(--v-ease-out)` on release, and the button `scale(0.97)` on press. Fire `reject()` on `transitionend` of the overlay. Keyboard: holding Space or Enter does the same via `keydown`/`keyup`. The label reads "Hold to reject". Do not build this unless README decision 2 says yes.

## Boundaries

- Do NOT auto-submit on the 6th digit. Approving money stays an explicit press.
- Do NOT add confetti, glow or bounce to the success.
- Do NOT change the API calls or `owner.code` handling.
- If an excerpt does not match, STOP and report.

## Verification

- **Mechanical**: `npm run check`. `npx playwright test e2e/activity-detail.spec.ts e2e/rules.spec.ts`. `make e2e-live`.
- **Feel check** (fixture, demo kitchen, request R-4 "waiting"):
  - Approve: the field rises in and focus is in it. Typing fills the cells one by one with a tiny pop, and the petrol cell walks right.
  - Type `111111` and submit: the cells shake once and turn red. Submit again: they shake again.
  - Type `246810` and submit: the notice folds away while "Waiting for you" becomes "Approved by you" through a soft blur. A moment later the Result row rises and a green check draws itself. At 10% playback it reads as one wave, not a queue.
  - Open an already ordered request: no check drawing, no rise.
  - Second tab: approve there. The first tab plays the same landing within about 2 s.
  - Reduced motion: no shake, no travel, short fades only. The caret does not blink.
  - Phone 390 px: the cells fit next to Cancel and Approve or wrap cleanly. Field and buttons share `--height-control`.
- **Done when**: the approval reads as one physical gesture from Approve to the check mark, and every test is green.
