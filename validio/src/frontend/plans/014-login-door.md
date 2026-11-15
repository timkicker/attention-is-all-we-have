# 014 — The door: an entrance worth a first visit, and a diagram that shows what Validio does

- **Status**: DONE
- **Commit**: 61a5322
- **Severity**: LOW (but the first thing every judge and new kitchen sees)
- **Category**: Missed opportunities (delight and explanation at the first-time tier)
- **Depends on**: 001, 003 (for the band's arrival after login)
- **Estimated scope**: 2 files (1 new component), ~200 lines

## Problem

`/login` (`src/routes/login/+page.svelte`) is a split page: a petrol panel with the wordmark and three sentences on the left, and the form and "Try the demo kitchen" on the right. It is seen once per visitor, the tier where motion may be generous, and it is fully static:

```svelte
<!-- src/routes/login/+page.svelte — current -->
<section class="panel" aria-label="About Validio">
  <div class="p-mark"><h1 class="wordmark">Validio</h1><span class="for">for Valio Aimo customers</span></div>
  <div class="p-copy">
    <p class="statement" data-testid="login-what">Let your agent order from Valio Aimo, inside the rules you set.</p>
    <p>Before every order, Validio asks Valio for the price and the stock. Your agent orders alone only below your limit; above it, the order waits for you.</p>
    <p>Every decision is written to a sealed record you can read at any time.</p>
  </div>
  <p class="p-foot">A service for restaurant kitchens buying from Valio Aimo.</p>
</section>
```

The product's whole idea (agent, then Validio checking Valio, then one of three outcomes) is told in prose. Switching between "Log in" and "Create account" makes three extra fields teleport in. Pressing "Try the demo kitchen" gives no feedback beyond a disabled button.

## Target

### A. Entrance (once per page load; marketing tier values from the choreograph skill)

| Element | Role | Starts | Duration | Motion | Relationship |
|:---|:---|:---|:---|:---|:---|
| Wordmark + "for Valio Aimo customers" | Lead | 0 ms | 600 ms | fade + `translateY(10px)`, `ease` | — |
| Statement (the first `p`) | Lead (same beat) | 0 ms | 600 ms | fade + `translateY(10px)` | Together with the wordmark |
| The two body paragraphs | Support | 120 ms | 500 ms | fade + `translateY(8px)` | Overlaps the lead |
| Flow diagram (B) | Support | 200 ms | 500 ms | fade + `translateY(6px)` | Overlaps |
| Foot line | Decoration | 260 ms | 400 ms | fade only | Overlaps |
| Form side (`.form-in`) | Support | 80 ms | 400 ms | fade only, no travel (the form must be usable at once) | Overlaps |

CSS only: `.enter > * { animation: v-door 0.6s ease both; animation-delay: var(--delay, 0ms); }` with `@keyframes v-door { from { opacity: 0; transform: translateY(var(--door-y, 10px)); } }`, and the per-element `--delay` / `--door-y` set through `style:` on each element. Reduced motion: `animation-name: v-fade` (opacity only) and `animation-delay: 0ms`. The fields are focusable and clickable from the first frame.

### B. Flow diagram (`src/routes/login/Flow.svelte`, inline SVG in the panel, under the copy)

Three columns: **"Your agent"**, then **"Validio"**, then three outcomes stacked: **"Ordered alone"**, **"Waits for you"**, **"Blocked"**. Lines are 1 px `var(--valio-band-muted)`, labels `--fs-cap` in `var(--valio-band-fg)`, outcome labels at 70% opacity when idle.

A packet (6 px square, `var(--valio-band-fg)`, `border-radius: var(--radius-chip)`) runs one cycle:

1. Agent to Validio: `translateX` along the segment, 600 ms `var(--v-ease-in-out)` (movement on screen).
2. At Validio a ring pulses once ("asks Valio"): scale 1 to 1.8, opacity 0.5 to 0, 400 ms `var(--v-ease-out)`.
3. Validio to the outcome of this cycle (cycling ordered, waits, blocked), 500 ms `var(--v-ease-in-out)`. That outcome's label goes to full opacity over 200 ms and back after 1.2 s.

Then a pause of 1.6 s. Total cycle about 4.3 s. It runs only while the tab is visible, and it starts 800 ms after load, once the entrance has settled. Drive it with WAAPI (`el.animate(...)` and `await anim.finished` in an async loop with an `alive` flag), not rAF. It stops when the component unmounts or `document.visibilityState === "hidden"`.

The SVG has `role="img"` and `aria-label="Your agent asks Validio. Validio checks Valio, then orders alone, asks you, or blocks."`. Reduced motion: no packet. All three outcomes show at full opacity and the diagram is static.

Phone (≤760 px): the panel stacks above the form. Show the diagram at `max-width: 320px`, or hide it if the panel would push the form below the first screen. Decide by looking at a 390 × 844 viewport.

### C. Log in ⇄ Create account

- The extra fields (Kitchen name; Valio customer number and Approval code) enter with `in:collapse` (260 ms) and leave with `out:collapse={{ duration: 160 }}`. They mount together, with no stagger.
- The heading "Log in" / "Create account": `{#key mode}` + `in:blurSwap`.

### D. Busy feedback (use plan 018's `BusyLabel` if 018 is done; these are its values)

While `busy`: the submit button's label becomes "Logging in" or "Creating account". The demo button's label becomes "Opening the kitchen", with lucide `LoaderCircle` (14 px) before it, spinning `animation: v-spin 800ms linear infinite` (constant motion, so `linear`). Keep the button width fixed (`min-width` equal to its idle width, measured once) so the layout does not shift.

### E. After login (with plan 003)

`goto("/")` from `/login` runs a view transition. The band has no old snapshot (the door has no band), so give it an entrance through `::view-transition-new(v-band):only-child { animation: v-band-in 400ms var(--v-ease-drawer) both; }` with `@keyframes v-band-in { from { transform: translateY(-100%); } }`. It slides down from the top edge once, on login only, because only then is there no old band.

## Repo conventions to follow

- Band colours: `--valio-band`, `--valio-band-fg`, `--valio-band-muted` (tokens.css). No literals.
- Copy rules (≤12 words per line, no dashes): the diagram labels above comply.
- Keep the testids: `login-what`, `login-submit`, `login-swap`, `try-demo`, `demo-code`, `login-problem`.

## Steps

1. `src/routes/login/+page.svelte`: add class `enter` to `.panel` and to `.form-side`. Set `style:--delay` / `style:--door-y` on each child per the table. Add the CSS from A in `<style>`.
2. Create `Flow.svelte` per B and place `<Flow />` between `.p-copy` and `.p-foot`.
3. Wrap the signup-only `VField`s in `<div in:collapse out:collapse={{ duration: 160 }}>` (one wrapper for the kitchen field, one for the customer and code pair). Key the heading.
4. Busy labels and spinner per D.
5. Add the CSS from E to `src/app.css` next to plan 003's block.

## Boundaries

- Do NOT add parallax, mouse-tracking, gradients, particles or glow to the panel.
- The diagram must not loop faster than once per ~4 s and must stop when hidden.
- The entrance runs on page load only, not on the mode switch.
- If an excerpt does not match, STOP and report.

## Verification

- **Mechanical**: `npm run check`. `npx playwright test e2e/login.spec.ts e2e/login-door.spec.ts`. `make a11y` (the SVG has a name, and the band text contrast holds during the entrance; axe runs with reduced motion).
- **Feel check**:
  - Load `/login` with a cold cache: the wordmark and statement rise together, then the body follows as a wave, and the form is there almost at once. Record it and scrub: no element waits for another to finish.
  - Watch the diagram for three cycles: one outcome lights per cycle, calm, with a long pause. Switch tabs and back: it resumes without a burst.
  - Create account: fields slide open together. Log in: they fold away faster than they came.
  - Try the demo kitchen: the label changes at once and the spinner turns. Landing on Home, the petrol band slides down once.
  - Reduced motion: everything fades in place, and the diagram is static with all outcomes lit.
- **Done when**: the door tells the product's story in motion once, and stays calm after.
