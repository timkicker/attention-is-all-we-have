# 013 — A command palette and a few keys, with no animation at all

- **Status**: DONE
- **Commit**: 61a5322
- **Severity**: LOW
- **Category**: New interaction (purpose & frequency: keyboard actions must not animate)
- **Depends on**: none (003's live cache improves the "Recent" group if present)
- **Estimated scope**: 2 new files, 2 edited, ~200 lines

## Problem

Everything in Validio takes a pointer: four nav words, filter buttons, rows. An owner who lives in the app, or a presenter on stage, has no fast way to say "go to the waiting order" or "pause the agent". The kit ships a command menu (`vendor/arlen-ui-kit/src/lib/components/ui/command/`: `Command`, `CommandInput`, `CommandList`, `CommandGroup`, `CommandItem`, `CommandEmpty`, `CommandShortcut`) that the app never uses.

## Target

**Palette**: ⌘K on macOS, Ctrl+K elsewhere, and a quiet "Search" button in the band on desk (lucide `Search` 16 px + "⌘K" in `--fs-cap`, `--valio-band-muted`).

- **No open or close animation and no selection-highlight transition.** A palette is opened 100+ times a day by people who use it. That is the "never animate" tier (Raycast has none). Open is instant, close is instant.
- Build it on the native `<dialog>` element (`showModal()`, `close()`). That gives focus containment and Escape for free, and avoids the kit `Dialog`, whose `rise` transition cannot be turned off without editing the kit. Style: `width: min(560px, calc(100vw - 32px)); margin-top: 12vh; padding: 0; border: 1px solid var(--v-line-strong); border-radius: var(--radius-modal); background: var(--v-surface); color: var(--v-fg)`. `::backdrop { background: var(--v-tint-strong); }`.
- Groups and items:
  - **Go to**: Home, Activity, Waiting for you (`/activity?status=waiting`), Blocked, Rules, Edit rules, Agent, Settings.
  - **Recent**: the newest 8 activity items (title, status word, amount) from `api.activity("all")`, fetched when the palette opens.
  - **Actions**: Pause agent / Resume agent (only when connected, through `agentApi.pause`), Connect agent (only when none, links to `/agent`), Theme: Light, Dark, System (through `setMode`), Start over (demo kitchens only, the same path as the demo bar's `reset()`), Log out (`logOut()`).
- Choosing an item closes the palette, then acts. Navigation through `goto`.

**Keys** (ignored while focus is in an input, textarea, select or contenteditable, while any modifier other than Shift is held, and while a dialog is open):

| Key | Does |
|:---|:---|
| `g` then `h` / `a` / `r` / `n` / `s` within 1 s | Go to Home / Activity / Rules / Agent (`n` for "agent", since `a` is Activity) / Settings |
| `j` / `k` on Activity and Home | Move focus to the next or previous `a.ar` row (`focus()`, `scrollIntoView({ block: "nearest" })`, **no smooth scroll**) |
| `1` to `5` on Activity | Choose filter All, Ordered, Waiting, Blocked, Standing |
| `?` | Open the palette with a "Keys" group listing the above |

Focus moves are instant. The existing `:focus-visible` outline (`src/app.css:12-15`) is the only feedback.

## Repo conventions to follow

- Kit components are imported as `@arlen/ui-kit/components/ui/<name>`. See `src/routes/+layout.svelte` for Button, Dialog and Input.
- Window-level listeners: `<svelte:window onkeydown={…} />`, not `onMount` + `addEventListener` (svelte-core-bestpractices).
- Copy: item labels as in the nav. No dashes.
- Theme: `setMode` from `src/lib/theme.svelte.ts`. Plan 016 adds a reveal origin; call it with no origin here (the centre of the screen).

## Steps

1. Create `src/lib/v2/Palette.svelte` with the native dialog and the kit Command parts, exposing `open()` through `export function open()` on the component (`bind:this`). Items are a typed array `{ group, label, hint?, run: () => void | Promise<void>, when?: () => boolean }`, rendered with `CommandItem onSelect`.
2. Create `src/lib/keys.ts` with a pure `keyRouter(e: KeyboardEvent, ctx)` that returns an action or null (unit-testable logic, and keeps the layout small). The `g` prefix state is a module variable with a 1 s timeout.
3. `src/routes/+layout.svelte`: mount `<Palette bind:this={palette} />` inside the logged-in branch. Add `<svelte:window onkeydown={onKey} />`. `onKey` handles ⌘K/Ctrl+K (`preventDefault`) and delegates the rest to `keyRouter`. Add the band button `#nav-search` on desk only (`{#if !chrome.phone}`), placed before `.kitchen`.
4. `src/routes/activity/+page.svelte`: no change needed for `1` to `5` if the router calls the page's `pick` through `goto` with the same URLs (`/activity`, `/activity?status=ordered`, …).
5. New spec `e2e/palette.spec.ts`: Ctrl+K opens it, typing "rules" and pressing Enter lands on `/rules`. `g` then `a` goes to `/activity`. `j` focuses the first row and Enter opens it. `?` lists the keys. Keys typed inside `#f-alone` on Rules edit do nothing.

## Boundaries

- Do NOT animate the palette, its items, its highlight or the focus moves. Not even a fade.
- Do NOT add single-letter shortcuts that act on money (approve or reject). Those stay explicit clicks with the code.
- No new dependencies.

## Verification

- **Mechanical**: `npm run check`, `npx playwright test`, `make a11y` (the dialog needs a name: `aria-label="Search and commands"`).
- **Feel check**: ⌘K, type "wai", Enter. You are on Waiting in under a second with nothing moving. Press `?` and read the list. On Activity, `j j k` walks rows with the focus ring. Typing `g` inside the Rules edit field types a "g".
- **Done when**: every page and every agent action is reachable without the pointer, and nothing in the palette animates.
