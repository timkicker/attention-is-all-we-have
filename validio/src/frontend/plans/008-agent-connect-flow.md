# 008 — Connecting the agent: states that hand over, a page that listens, a code that reveals itself

- **Status**: DONE
- **Commit**: 61a5322
- **Severity**: MEDIUM
- **Category**: Missed opportunities (state indication, spatial consistency, delight at a first-time moment)
- **Depends on**: 001
- **Estimated scope**: 1 file (`src/routes/agent/+page.svelte`), ~110 lines

## Problem

The Agent page is a state machine, `none → pairing → consent → active ⇄ paused` (`src/routes/agent/+page.svelte:97-162`). It is the live demo's main beat: the presenter adds the MCP address in their agent, the agent calls, and the code appears here through polling. Today:

- Every state change swaps the whole block in one frame.
- In `pairing`, nothing says the page is waiting for anything. It shows an address and nothing else, so it looks finished:
  ```svelte
  <!-- src/routes/agent/+page.svelte:108 — current -->
  <p class="pair-h" id="pair-h" data-testid="mcp-hint">Add this address to your agent as an MCP server, then ask it to order something.</p>
  ```
- The verification code, the one thing to compare with the agent's screen, just appears:
  ```svelte
  <!-- :137-139 — current -->
  <p class="verify-code mono" id="verify-code" data-testid="verify-code" data-raw aria-label="Code {a.consent.verifyCode?.split('').join(' ')}">
    {a.consent.verifyCode ?? ""}
  </p>
  ```
- The Copy buttons change their label "Copy" to "Copied" (`:64-68`), and the button width jumps.

## Target

| Moment | Motion | Values |
|:---|:---|:---|
| State to state (`none`, `pairing`, `consent`, connected) | The outgoing block leaves instantly. The incoming block rises in | `in:rise={{ y: 8, duration: 260 }}`. Local, so no animation on first load |
| Pairing: "waiting for the first call" | A new status line with a petrol dot and a slow ring. An idle loop is allowed here because it signals a live connection | dot 8 px `background: var(--valio)`. Ring: `::after` `inset: 0; border: 1.5px solid var(--valio); border-radius: var(--radius-chip)` (the token; the dot itself uses `--radius-chip` too); `animation: v-listen 2000ms var(--v-ease-out) infinite`, `from { transform: scale(1); opacity: 0.5 } to { transform: scale(2.6); opacity: 0 }`. Reduced motion: no ring |
| Consent: the code arrives | Each character reveals, a non-uniform stagger (rare, first-time: the delight tier) | 7 characters including the dash. Delays `0, 40, 75, 105, 130, 150, 165 ms`. Each `animation: v-char 300ms var(--v-ease-out) both` from `opacity: 0; transform: translateY(8px); filter: blur(4px)`. Reduced motion: one 120 ms fade, no delays |
| Allow, then connected | The connected block rises in (row 1). The page-head pill swaps through `{#key}` + `blurSwap` | as row 1. Pill: `blurSwap` 200 ms |
| Pause and Resume | The pill swaps through `blurSwap`. Nothing else moves | 200 ms |
| Copy, then Copied | Icon and label crossfade inside a fixed-width button | Lucide `Copy` to `Check`; `{#key copied === what}` + `in:blurSwap={{ duration: 150 }}`; button `min-width: 92px` |

Copy for the new line (≤12 words, no dashes): "Waiting for your agent's first call".

## Repo conventions to follow

- Keep the app's existing copy style: short plain sentences, no dashes or middle dots.
- Keep `data-testid`: `mcp-hint`, `mcp-url`, `copy-mcp`, `verify-code`, `consent-allow`, `consent-deny`, `agent-state`, etc. `e2e/agent.spec.ts:90` asserts `verify-code` **text** with `/^[A-Z2-9]{3}-[A-Z2-9]{3}$/`. Spans for each character keep `textContent` identical, and `aria-label` stays on the `<p>`.
- `e2e/agent.spec.ts:97` sets `textContent` on `verify-code` directly. That keeps working with child spans.

## Steps

1. Script: import `rise`, `blurSwap` and `reduced` from `$lib/motion`, and `Check` and `Copy` from `@lucide/svelte`.
2. Wrap the root element of each state branch (`<Section class="v-card">` in `none`, `<section class="pair">`, `<section class="consent">`, and `<ListSection id="agent">` for connected) in `<div in:rise={{ y: 8, duration: 260 }}>`. ListSection and Section are components, which cannot take transitions directly.
3. In the pairing branch, after `.pair-h`, add:

   ```svelte
   <p class="listen" role="status" data-testid="agent-listening">
     <span class="dot" aria-hidden="true"></span>Waiting for your agent's first call
   </p>
   ```

   ```css
   .listen { display: flex; align-items: center; gap: 10px; margin: 12px 0 0; font-size: var(--fs-meta); line-height: var(--lh-meta); color: var(--v-muted); }
   .dot { position: relative; width: 8px; height: 8px; border-radius: var(--radius-chip); background: var(--valio); flex: none; }
   .dot::after { content: ""; position: absolute; inset: 0; border: 1.5px solid var(--valio); border-radius: var(--radius-chip); animation: v-listen 2000ms var(--v-ease-out) infinite; }
   @keyframes v-listen { from { transform: scale(1); opacity: 0.5; } to { transform: scale(2.6); opacity: 0; } }
   @media (prefers-reduced-motion: reduce) { .dot::after { animation: none; opacity: 0; } }
   ```
4. Verification code:

   ```svelte
   <p class="verify-code mono" id="verify-code" data-testid="verify-code" data-raw aria-label="Code {a.consent.verifyCode?.split('').join(' ')}">
     {#each (a.consent.verifyCode ?? "").split("") as ch, i (i)}<span class="vc" style:--d="{[0, 40, 75, 105, 130, 150, 165][i] ?? 165}ms" aria-hidden="true">{ch}</span>{/each}
   </p>
   ```

   ```css
   .vc { display: inline-block; animation: v-char 300ms var(--v-ease-out) var(--d) both; }
   @keyframes v-char { from { opacity: 0; transform: translateY(8px); filter: blur(4px); } }
   @media (prefers-reduced-motion: reduce) { .vc { animation: v-fade 120ms linear both; } @keyframes v-fade { from { opacity: 0; } } }
   ```

   `style:--d` sets a custom property on the span itself, not a parent, so there is no inherited style recalculation. The `aria-hidden` spans are fine because the `<p>` carries `aria-label`.
5. Copy button snippet:

   ```svelte
   <Button variant="outline" class="copy-btn" …>
     {#key copied === what}
       <span class="cb" in:blurSwap={{ duration: 150 }}>
         {#if copied === what}<Check size={14} aria-hidden="true" />Copied{:else}<Copy size={14} aria-hidden="true" />Copy{/if}
       </span>
     {/key}
   </Button>
   ```

   with `:global(.copy-btn) { min-width: 92px; }` and `.cb { display: inline-flex; align-items: center; gap: 6px; }`.
6. Page-head pill (facts snippet): `{#key pill.label}<span in:blurSwap><VPill …/></span>{/key}`.

## Boundaries

- Do NOT add an exit animation to the outgoing state. Two stacked states inside a resizing block look broken.
- Do NOT animate the MCP URL text, the "What it may do" list or the connected rows individually. One entrance per container.
- The listening ring is the only infinite animation on this page. Nothing else idles.
- If an excerpt does not match, STOP and report.

## Verification

- **Mechanical**: `npm run check`. `npx playwright test e2e/agent.spec.ts`. `make e2e-live` (a real MCP client connects).
- **Feel check** (fixture: Connect agent, then run `validioMcpCall()` in the console):
  - Connect agent: the pairing block rises in and the dot starts breathing. The ring is slow and quiet, not a beacon.
  - Run `validioMcpCall()`: the code assembles left to right as a wave, the first characters faster than the last. At 10% playback the gaps shrink.
  - Allow: the connected rows rise in and the pill "Check the code" turns into "Active" softly.
  - Copy: the icon turns into a check and the button does not change width.
  - Reload while in `consent`: the code still animates once (acceptable, rare). Reload while `active`: nothing moves.
  - Reduced motion: no ring, no stagger, fades only.
- **Done when**: every state change on Agent has a single clear entrance and the page visibly listens while pairing.
