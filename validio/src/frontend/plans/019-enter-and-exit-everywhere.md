# 019 — Enter and exit for everything that appears or goes away

- **Status**: DONE
- **Commit**: 61a5322
- **Severity**: MEDIUM
- **Category**: Missed opportunities (preventing a jarring change), Interruptibility
- **Depends on**: 001 (`rise`, `collapse`, `blurSwap`, tokens). Coordinates with 004, 005, 007, 008, 016 (see "Already covered")
- **Estimated scope**: ~12 files, small edits each

## Problem

Plans 004 to 016 give motion to the big moments. The rest of the app still has dozens of small `{#if}` blocks that pop in and out in one frame and shove the layout: error lines, hints, notices, conditional rows, swapped words. Each is small, and together they make the app feel unfinished.

## The rules for this plan (from the animate and choreograph skills)

- **Enter**: `ease-out`, start close to the final state (`opacity 0` plus a 4 to 6 px rise or a height reveal). Never from `scale(0)`.
- **Exit**: shorter than the enter (about 60 to 75%), simpler (fade or fold), the same direction it came from.
- **Something that takes layout space** (a line under a field, a row) grows and shrinks its height (`collapse`), so the content below glides instead of jumping. **Something that replaces text in place** swaps with `blurSwap`, with no height change.
- **Local transitions only** (Svelte 5's default): nothing plays on first render. A page that loads with an error already showing does not animate it.
- **Errors arrive and stay put.** No shake except the approval code (plan 007), no colour pulse.
- Reduced motion: the helpers turn everything into 120 ms fades (plan 001).

## Inventory: every conditional piece and its motion

| # | Where (file:line at 61a5322) | What appears | Enter | Exit |
|:---|:---|:---|:---|:---|
| 1 | `src/lib/v/VField.svelte` (markup, `{#if problem}…{:else if hint}`) | the problem line replaces the hint under a field | `{#key problem ? "p" : "h"}` + `in:blurSwap={{ y: 3 }}`. The help line keeps its height (both are one line), so nothing moves | none (the new one covers) |
| 2 | `src/routes/settings/Form.svelte:27` | `.sf-problem` form-level error | `in:collapse={{ duration: 200 }}` | `out:collapse={{ duration: 140 }}` |
| 3 | `src/routes/rules/UnitField.svelte:49` | `.uf-problem` under a Rules field | `in:collapse={{ duration: 200 }}` | `out:collapse={{ duration: 140 }}` |
| 4 | `src/routes/login/+page.svelte:113` | `login-problem` | `in:collapse={{ duration: 200 }}` | `out:collapse={{ duration: 140 }}` |
| 5 | `src/routes/agent/+page.svelte:167` | `agent-problem` | `in:rise={{ y: 4, duration: 200 }}` | fade 140 ms |
| 6 | `src/routes/activity/[id]/+page.svelte:201` | `.ask-problem` (Reject failed, already answered) | `in:rise={{ y: 4, duration: 200 }}` | fade 140 ms |
| 7 | `src/routes/+layout.svelte:200` | token dialog `.bad` line | `in:collapse={{ duration: 200 }}` | — |
| 8 | `src/routes/rules/edit/+page.svelte:~244` | `rules-changes` line: "No changes yet", then "2 changes, in Money", then a form problem | `{#key formProblem || changeLine}` + `in:blurSwap={{ duration: 160 }}`. Same line, same height | — |
| 9 | `src/routes/rules/edit/+page.svelte:203-205` | row descriptions: "Was 1,200.00 €" replacing "Above it, blocked" | **skipped**: the kit `Row` takes `description` as a plain string (`row/row.svelte:32`, checked on 15 Nov). Keying the whole row would remount the input inside it and steal focus. Leave it instant | — |
| 10 | `src/routes/rules/edit/+page.svelte:231-238` | `row-extra` appears when "From Valio's list" is picked | wrap in `<div in:collapse>` (the `ListSection` hairline moves onto the wrapper, as in plan 005) | `out:collapse={{ duration: 180 }}` |
| 11 | `src/routes/rules/edit/+page.svelte` (`row-allowed` description) | "Each substitute waits for you" swapping with "Not on the list: waits for you" | **skipped**, for the same reason as #9 | — |
| 12 | `src/routes/rules/+page.svelte:43-45` | the `rules-saved` Notice after a save | `in:rise={{ y: 6, duration: 260 }}`, and `.v-glow` on the rows whose values changed (pass `?saved=alone,week` from the edit page, a comma list of row ids) | stays until navigation |
| 13 | `src/lib/v/VState.svelte:27-32` | "Still loading 12 s" line | `in:rise={{ y: 4, duration: 200 }}`. The seconds tick with no animation (a counter the user is reading) | — |
| 14 | `src/routes/+page.svelte` lede (`home-lede`) | "Nothing needs you right now." to "One order waits for you." | `{#key WAITS(h.needsYou.length)}` + `in:blurSwap` | — |
| 15 | `src/routes/+page.svelte` lede (`home-agent`) | "Kitchen agent is active." to "is paused." | `{#key h.agent.state}` + `in:blurSwap` | — |
| 16 | `src/routes/+layout.svelte` band `.k-name` | the kitchen name after a rename in Settings | `{#key session.account.name}` + `in:blurSwap` | — |
| 17 | `src/routes/+layout.svelte` `.nb` badge (the box itself, not the number) | the waiting badge appears when the first order waits | `in:` fade + `scale(0.9) → 1`, 200 ms `easeOut`; the transform origin is the left edge | `out:` fade 140 ms |
| 18 | `src/routes/settings/Code.svelte`, `Kitchen.svelte`, `Login.svelte` (`done` states) | the "changed" confirmations | follows plan 016's "Saved" pattern | — |
| 19 | Demo "Start over" (`+layout.svelte` `reset()`) | the whole kitchen goes back to the sample | wrap `api.reset()` + `bump()` + `goto("/")` in `document.startViewTransition` (when available and motion is allowed). Root crossfade 200 ms `--v-ease-out`. It reads as "the page was replaced", not as a glitch | — |
| 20 | Kit `Dialog` (token dialog) and kit `ConfirmDialog` (Disconnect) | modals | already animated by the kit (`dim` + `rise`, 250 ms `cubicOut`, symmetric). **Leave it**: the kit is not edited, and modals are centred and exempt from origin rules | — |

### Already covered elsewhere (do not duplicate)

- Page content arrival and skeletons: 004. Live rows: 005. Folds: 006. The approve field, `.ask`, status word and result: 007. Agent states, copy buttons and the pill: 008. Home figures and checklist: 009. Settings edit forms and "Saved": 016. Login fields and heading: 014. Toasts: 012.

## Repo conventions to follow

- Import helpers from `$lib/motion`. Keep every `id`, `data-testid` and `role="alert"`. A `role="alert"` element must be in the DOM with its text when it appears. `in:` keeps it in the DOM from the first frame, so screen readers still announce it.
- When a transition must sit on a component (`ListRow`, `Notice`), wrap it in a `<div>`. Check that the wrapper does not break the `.section-card > * + *` hairline rule (`src/app.css:318-320`). The wrapper becomes the direct child, which is the intent.

## Steps

1. Work through the inventory top to bottom. One commit per file group is fine.
2. #9 and #11 are skipped (see the table). Do not edit the kit to make them possible.
3. For #12: in `src/routes/rules/edit/+page.svelte` `save()`, compute which of `alone`, `waiting`, `week`, `allowed`, `extra`, `must`, `never` changed and `goto("/rules?saved=" + list.join(","))`. In `src/routes/rules/+page.svelte`, read the list and add `class="v-glow"` to the matching `ListRow` wrappers. The existing `saved` check (`searchParams.has("saved")`) keeps working.
4. For #19: the reset path:
   ```ts
   async function reset() {
     demoProblem = "";
     const run = async () => { await api.reset(); bump(); await goto("/"); };
     try {
       if (document.startViewTransition && !reduced()) await document.startViewTransition(run).finished;
       else await run();
     } catch (e) { /* existing handling */ }
   }
   ```
   Keep the existing `catch` body exactly. Note: if `api.reset()` throws inside the transition callback, the transition aborts and the error still reaches the `catch` through `.finished`. Verify the token-dialog path (a 401 or 403 opens the dialog) still works.

## Boundaries

- Do NOT animate data values inside rows, tables or checks (amounts, times, counts in filters).
- Do NOT add exit animations to whole pages (plan 003 owns navigation).
- Do NOT edit the kit.
- If an excerpt does not match, STOP and report.

## Verification

- **Mechanical**: `npm run check`. `npx playwright test` (login, settings, rules and agent specs assert the problem texts and testids). `make a11y`: alerts are announced.
- **Feel check**:
  - Login with an empty form: the problems slide open under their fields. Type: they swap or fold away and the form below glides.
  - Rules edit: type 9000 into "Ordered alone". "Was 1,200.00 €" swaps in, and the change line swaps to "1 change, in Money". Switch Substitutes to "Never": the Extra cost row folds away and the section closes up. Switch back: it unfolds.
  - Save: the Rules page shows the notice rising in, and the changed rows glow once.
  - Rename the kitchen in Settings: the name in the band crossfades.
  - Demo bar, Start over: the page crossfades to the fresh kitchen.
  - At 10% playback, every exit is visibly faster than its enter.
- **Done when**: no conditional piece of UI in the inventory pops in or out, and nothing animates on first render.
