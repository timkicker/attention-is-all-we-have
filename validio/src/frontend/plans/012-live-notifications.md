# 012 — Live notifications: the agent's news reaches you on any page

- **Status**: DONE
- **Commit**: 61a5322
- **Severity**: MEDIUM
- **Category**: Missed opportunities (state indication, spatial consistency); new interaction
- **Depends on**: 001
- **Estimated scope**: 3 new files, 1 edited, ~220 lines

## Problem

The layout already polls `api.home()` every 2 s for the waiting count (`src/routes/+layout.svelte:50-60`):

```ts
let waiting = $state(0);
const count = async () => {
  if (!session.account) return;
  waiting = (await api.home()).needsYou.length;
};
onMount(() => poll(count));
```

So the app *knows* the moment the agent asks for approval, the moment it orders alone, and the moment it calls for pairing. It tells you only through a small number on "Home". An owner reading Rules or Settings misses it, and so does a demo audience.

The browser tab always says "Validio", so a waiting approval is invisible from another tab.

## Target

**A. A toast region** (`src/lib/v2/Toaster.svelte` + `src/lib/toast.svelte.ts`), hand-rolled. No dependency is needed for three toast kinds.

- Placement: desk at the bottom right, `right: 24px; bottom: 24px; width: 360px`. Phone: `left: 16px; right: 16px; bottom: calc(56px + env(safe-area-inset-bottom) + 12px)`, above the dock.
- At most 3 visible, newest at the bottom, older ones pushed up with `animate:flip={{ duration: 400, easing: ease }}`.
- Enter (Sonner recipe): `opacity 0 → 1`, `translateY(100%) → 0`, **400 ms `ease`**. A toast is the documented exception to the 300 ms budget and uses Sonner's `ease`. Implement it as a Svelte `in:` with `easing: ease` from `$lib/motion`, since the element mounts with JS.
- Exit: the same edge, `translateY(100%)` plus fade, 400 ms `ease` (`out:`). On swipe-dismiss it leaves in the swipe direction.
- Auto-dismiss after 6 s. The timer **pauses** while the pointer is over the region or focus is inside it, and resumes after.
- Swipe to dismiss (phone): drag horizontally 1:1 (`setPointerCapture`). Dismiss when `|dx| > 80px` **or** velocity `|dx| / ms > 0.11`. Otherwise spring back with `transition: transform 200ms var(--v-ease-out)`. Past 0 in the wrong direction, apply friction (`dx × 0.2`).
- Each toast: a title line (`--fs-body`, 500), one body line (`--fs-meta`, `--v-muted`), an optional action link (petrol), and a close button (lucide `X`, 32 × 32 hit area, `aria-label="Dismiss"`).
- Look: `background: var(--v-surface); border: 1px solid var(--v-line-strong); border-left: 2px solid <tone>; border-radius: var(--radius-card); padding: 12px 14px`. No shadow (tokens set `--shadow-card: none`). Tone rule: waiting `var(--valio)`, ordered `var(--v-ok)`, blocked `var(--v-bad)`.
- Accessibility: the region is `<section aria-label="Notifications">` with an `aria-live="polite"` list. Toasts never take focus. Escape while focus is inside dismisses the focused toast.
- Reduced motion: 120 ms fades, no travel, no flip.

**B. What raises a toast** (diffing the same `home()` answer the layout already fetches):

| Event | Toast (≤12 words, no dashes) | Action |
|:---|:---|:---|
| A new id appears in `needsYou` | Title "Waiting for you". Body: `{title}, {money(totalCents)}` | "Review" to `/activity/{id}` |
| `agent.state` becomes `consent` | Title "Your agent called". Body: "Check the code before you allow it" | "Agent" to `/agent` |
| A new `latest` item with status `blocked` | Title "Blocked". Body: `{title}` | "See why" to `/activity/{id}` |
| A new `latest` item with status `ordered` | Only if README decision 4 says yes. Title "Ordered alone". Body: `{title}, {amount}` | "Open" |

Rules:
- Never on the first poll after login, reload or reset: seed the "seen" sets first.
- Never for an item whose page is open (`page.url.pathname === /activity/{id}`), and not the consent toast while on `/agent`.
- Never for the owner's own action in this tab. The approve flow calls `bump()`, which re-seeds the seen sets.

**C. Tab title**: `<title>{waiting > 0 ? `(${waiting}) Validio` : "Validio"}</title>` (README decision 3).

## Repo conventions to follow

- Shared state as a `*.svelte.ts` module, like `src/lib/chrome.svelte.ts`.
- Colours and radii from tokens only (`check-tokens.mjs`).
- Copy rules: one clause, ≤12 words, no middle dot or dashes. Money via `money()`.

## Steps

1. `src/lib/toast.svelte.ts`:

   ```ts
   export type Tone = "wait" | "ok" | "bad";
   export interface Toast { id: number; tone: Tone; title: string; body?: string; action?: { href: string; label: string } }
   let next = 1;
   export const toasts = $state<{ list: Toast[] }>({ list: [] });
   export function toast(t: Omit<Toast, "id">) {
     toasts.list = [...toasts.list, { ...t, id: next++ }].slice(-3);
   }
   export function dismiss(id: number) {
     toasts.list = toasts.list.filter((t) => t.id !== id);
   }
   ```
2. `src/lib/v2/Toaster.svelte`: renders `toasts.list` in a keyed each with `in:`, `out:` and `animate:flip` as specified, plus timers (a per-toast `setTimeout` stored in a plain `Map`, paused through `onpointerenter`/`onpointerleave`/`onfocusin`/`onfocusout` on the region) and the swipe handlers. Clicking an action dismisses the toast.
3. `src/routes/+layout.svelte`:
   - Mount `<Toaster />` once inside the `{:else if session.account}` branch, after the dock.
   - Change `count()` to keep the whole answer and diff it:
     ```ts
     let seenWaiting: Set<string> | null = null;
     let seenLatest: Set<string> | null = null;
     let lastAgent = "";
     const count = async () => {
       if (!session.account) return;
       const h = await api.home();
       waiting = h.needsYou.length;
       const here = page.url.pathname;
       if (seenWaiting && seenLatest) {
         for (const i of h.needsYou) if (!seenWaiting.has(i.id) && here !== `/activity/${i.id}`) toast({ tone: "wait", title: "Waiting for you", body: `${i.title}, ${money(i.totalCents ?? 0)}`, action: { href: `/activity/${encodeURIComponent(i.id)}`, label: "Review" } });
         for (const i of h.latest) if (!seenLatest.has(i.id) && i.status === "blocked" && here !== `/activity/${i.id}`) toast({ tone: "bad", title: "Blocked", body: i.title, action: { href: `/activity/${encodeURIComponent(i.id)}`, label: "See why" } });
         if (h.agent.state === "consent" && lastAgent !== "consent" && here !== "/agent") toast({ tone: "wait", title: "Your agent called", body: "Check the code before you allow it", action: { href: "/agent", label: "Agent" } });
       }
       seenWaiting = new Set(h.needsYou.map((i) => i.id));
       seenLatest = new Set(h.latest.map((i) => i.id));
       lastAgent = h.agent.state;
     };
     ```
     Reset `seenWaiting = seenLatest = null` in an `$effect` on `chrome.version` (a bump) and when `session.account?.id` changes.
   - Update `<svelte:head><title>` as in section C. Note: `VHead` calls `setTitle()` into `chrome.title`, which is not rendered into `<title>`. Leave that as is.
4. New spec `e2e/toasts.spec.ts`: log into the demo, open `/rules` in page A, approve R-4 in page B (same context), and check that page A does **not** toast (an approval removes, it does not add). Then `reset` in B and check that A shows no toast for the re-seeded items. A positive test needs the live backend: add one to `e2e-live/flow.demo.ts` where the agent scene creates a waiting order while `/rules` is open, expecting a toast with the title "Waiting for you" and an action "Review" that navigates.

## Boundaries

- Do NOT toast confirmations of the owner's own clicks (they already get inline feedback).
- Do NOT add sound, browser Notifications API permission prompts, or badges on the favicon.
- No new dependency (svelte-sonner is not needed).
- If an excerpt does not match, STOP and report.

## Verification

- **Mechanical**: `npm run check`, `npx playwright test`, `make e2e-live`.
- **Feel check**:
  - Live mode on `/settings`, run `make agent SCENE=2`. A toast slides up from the bottom edge, unhurried. Hover it: it stays. Leave: it goes after a few seconds, down the same edge.
  - Three quick events: they stack and older ones glide up together. A fourth pushes out the oldest.
  - Phone: flick a toast sideways fast and short: it dismisses (velocity). Drag slowly 40 px and let go: it springs back.
  - Approve in this tab: no toast. Tab title shows "(1) Validio" while one order waits.
  - Reduced motion: fades only.
- **Done when**: the three events reach the owner on any page, and nothing else ever toasts.
