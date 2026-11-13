# Validio web app: UI plan

This file is the plan for the kitchen's web app. The pages follow it, so change the plan before you change a page.

The first UI was torn down on 14 Nov. It was crammed, it leaned on yellow, amber and beige, and it had little to do with the SDK. None of its layout, colours, boxes or page components survive.

What remains:
- the data layer in `src/lib/api` (types, client, mock fixture)
- `poll.ts`
- the money and time helpers in `format.ts`
- the scene logic that the e2e tests check

## Direction

Validio is an Arlen app: the kitchen's window onto what its buying agent did. It has the same skeleton as every Arlen app. A shell-coloured sidebar sits on the left. A 40px content bar runs across the top with the sidebar toggle, a hairline and where you are. Under the bar is a list, a timeline or a settings column, dark by default.

Each screen answers three questions in order, and only the first is fully open:
1. What happened? A short title and one figure.
2. Why? One sentence.
3. Can I trust it? The evidence, folded away until someone asks for it.

## Rules from Tim and the reviews

**From Tim**
- Less on one screen, with more air. Use progressive disclosure: the default view holds the decision and nothing it does not need.
- No yellow, amber, ochre, beige, cream or sepia anywhere, not even for a warning. The kit's `warn` Badge, `caution` Notice and `--color-warning` are therefore never used. The amber that Arlen uses for "worth your eyes" becomes words, an icon and the accent mark.
- Build on the kit's own components and tokens, not lookalikes.
- No purple gradients, glow, emoji labels or anything else that looks generated.

**From the Arlen review**
- Every copy line is one clause of at most 12 words. Two short sentences are allowed only as the body under a question.
- Money has one shape, `1,010.00 €`.
- Use no middle dot as a separator and no m-dash.
- The app name is not in the sidebar.

## References and what we take from each

Sources:
- the review files `tmp/ui-review-{website,halbat,arlen}.md`
- Arlen renders in `tmp/arlen-shots/`
- the live website in `tmp/ui-website/`
- `validio/artifacts/refs/`

The website's current design is `origin/main:app/kit.css`, which is built on halbat's `src/lib/kit/halbat.css` with Arlen's control heights.

| Reference | What we take | What we leave |
|:---|:---|:---|
| Arlen mail (`mail-open-1280.png`) | The inbox as a list column (21rem) and a reading pane. The neutral sample Notice at the top of the list. A `SegmentedControl` filter. Borderless rows (hover at fg 5 %, selected at fg 9 %) with the name and time on top, then the outcome and a one-line reason. The unread mark: a 0.4rem `--radius-chip` square in the accent. Counts as quiet numbers in the sidebar | Search, compose, the window buttons |
| Arlen knowledge (`knowledge-1280.png`) | The Open Ledger as a timeline. Caps group heads. One grid row per entry: `icon / verb (right-aligned, quiet) / object / source / time`. The details are a collapsible row. The sidebar's second group, AUTHORITY | The time scrubber |
| Arlen settings App access (`settings-privacy-1280.png`) | The Spend Pass as a capability grant: a grantee card with an initial tile and rows of the form `quiet verb / strong object / quiet provenance / action`. `LinkCard` as a door | The By app / By capability pivot |
| Arlen settings and system monitor | Steady orders as a settings panel: `Page`, `StatGrid`, a `Section` of `Row`s, and row actions in the 200px control column | |
| tim.kicker.dev | On the phone: a bottom bar and a header line with a back arrow (Arlen has no phone layout). Inter with `cv11`/`ss01`. Mono only for IDs and hashes. The steel accent | The website's own sidebar and token names: the kit's are used |
| halbat (current kit, `tmp/halbat-shots/`) | Density for tables and meta lines. A facts line under a title (value in fg 500, label muted, 24px gaps) instead of a row of stat tiles. Record lists as rows or tables with hairlines and right-aligned tabular numbers, never a card per item. The 8px spend bar with a tick at the limit. Drift bars where the weeks that matter are in fg and the average is a context line. Caveats sit behind an info popover rather than as a standing paragraph. No middot, en dash or em dash in UI text | The ochre accent and the orange warn pill, which Tim rules out |

## Theme

Dark by default: the kit's shipped Arlen Dark (`#0a0a0a` shell, `#0f0f0f` app, `#171717` card), with depth from surface lightness and no shadow. On a projector `#fafafa` on `#0f0f0f` is 19:1 and the secondary `#a1a1aa` is 7.6:1.

Light also works. It is the kit's own `theme-light.css` (`:root[data-theme="light"]`), set when the system asks for light or with `?theme=light`. Validio's light overrides are only the accent pair, and the light theme has no warm tint. Every screen is shot in both themes.

## Colour

Validio sets only these kit tokens, in `src/app.css`:

| Kit token | Value | Why |
|:---|:---|:---|
| `--color-accent` | `#3d6590` | The steel from the family. White text on it is 6.6:1. It fills the primary button and the progress bar and marks the unread square. It is not green, which means "ordered" here, and not ochre, which is halbat's |
| `--color-accent-hover` | `#4a73a0` | The hover step |
| `--color-accent-foreground` | `#ffffff` | Text on the accent |
| `--ring` | `#7f9fc4` | The focus ring, lighter so it reads on the card |
| `--font-size-base` | `15px` | The projector. The whole ladder follows |
| `--sidebar*` | as in Arlen mail's `app.css` | The kit sidebar paints nothing without them |

How each state is shown, always with the kit's own tokens:

| State | How it shows |
|:---|:---|
| ordered alone, ordered, approved, chain verified | text in the kit's success-text mix (`color-mix(--color-success 76 %, --foreground)`), with an icon where a row has one |
| blocked, rejected, contradicted, chain broken | `--destructive-on-tint` text, with an icon |
| waiting for you | the accent square plus the words "Waiting for you" in primary text. It is a call to act, not a danger |
| ranked, attested, consistent, unchecked, not deliverable, drift | the word in secondary text. The word carries the meaning |
| product numbers and order ids | `Badge variant="outline"`, as knowledge does for projects |
| example data, simulated stock-out, simulated history | `Notice tone="neutral"` in the Arlen sample shape ("Example orders, not this kitchen's real ones.") |

## Type

The kit's Inter Variable and its base-relative ladder off 15px: `2xs` 12, `xs` 13, `sm` 14, `base` 15, `md` 16, `lg` 18, `xl` 21.

- Page and pane titles are `xl`/600. The content bar title is `sm`/500.
- Group heads are the kit's caps labels, `2xs`/600/.1em. These are Arlen's and they stay.
- Meta and times are `2xs` secondary with `tabular-nums`.
- The one big figure per screen is 2rem/600 tabular.
- Mono (`ui-monospace`) is used only for hashes.
- `font-feature-settings: "cv11","ss01"` is set on `body`.

## Layout

**Desktop (1024 and up).**
- `SidebarProvider`, then `Sidebar collapsible="icon"` (16rem, icon rail 3rem), then `SidebarInset`.
- **Sidebar head band** (40px): an initial tile "H" plus "Hotel Espoo kitchen". The word "Validio" is in `<title>` and in a screen-reader-only `h1`.
- **Sidebar group without a label**: Inbox (lucide `Inbox`, with the number waiting as a quiet count), Steady orders (`CalendarSync`), Open ledger (`ScrollText`).
- **Group AUTHORITY**: Spend Pass (`ShieldCheck`).
- **Sidebar footer**: the frozen clock, `2xs` secondary with `tabular-nums`.
- **Content bar**: `SidebarTrigger`, a vertical `Separator`, the bar title, a spacer, and an `IconAction` (`FlaskConical`, "Demo controls") that opens a `Popover` holding "Simulate stock-out" and "Start over".
- **Inbox and request**: one split. The list column is `flex: 0 1 21rem` and the pane takes the rest. `/` selects the first request; `/requests/[id]` selects that one.
- **Steady, Spend Pass and ledger**: `Page` inside a 46rem column. These use the kit's `--width-section-body`, so the title lines up with the cards.

**Phone (760 and below).**
- The sidebar is hidden. A 48px header line holds the title, plus a back arrow on detail pages.
- A bottom bar holds Inbox, Steady and Ledger, each as a 20px icon over a 12px label. This comes from the website, because Arlen has no phone layout.
- `/` shows only the list and `/requests/[id]` shows only the pane.
- The approve page has no bar. It has one question, one proposal, then Reject and Approve, both 44px and the same size.

## Disclosure, screen by screen

| Screen | Visible at once | Opens on request |
|:---|:---|:---|
| Inbox list | The sample Notice, the filter (All / Waiting / Blocked) and the rows. A row is the request name and its time, the outcome and the total, and one clause of reason | the request, in the pane |
| Request pane | The title ("1000 cartons of lactose-free milk"). One `Section` card holding the outcome as icon and text, the total as the big figure, the agent's sentence in secondary and "Checked 9 products live". Under it, a `Progress` bar for the Spend Pass ("1,010.00 € of 1,200.00 € allowed alone"). When the request is waiting, the card holds "Open approval" as the primary button | "Ranked options (7)" as a `Collapsible`. Each option is a verb row: `chosen / Valio Arki Eila 1 l / 464306 / 1,010.00 €`. Each row's facts open one level deeper, with the grade as a word. Substitutes and options beyond the list open the same way. A `LinkCard` leads to the Spend Pass |
| Approve (390) | The question in at most 12 words ("Order grated Maestrella for 196.60 €?"), two short body sentences, the proposal card, then Reject and Approve | "Why not the others (4)" as verb rows |
| Approve, done | One sentence ("Ordered. Valio was asked again first.") and three timeline rows | |
| Spend Pass | The grant card: tile "B", "agent:buyer-1", "Signed by the kitchen". The rows are `may order alone / up to 1,200.00 €`, `never above / 2,000.00 €`, `only / lactose free`, `deliver by / 16 Nov`, `valid until / 17 Nov` | "What the agent sees" as one collapsible row |
| Steady orders | One `LinkCard` per order | the order |
| Steady order | `Page` with the back door, the neutral Notice that the history is simulated, a facts line (4 lines, this week's total, change against usual) and Renew as the primary button | After renewal, a `Section` of rows, one per line, with the result as text and its action in the control column. Each line's detail (the split, the substitute, the 8-week drift chart) is collapsible |
| Open ledger | The chain status as the first line (`ShieldCheck` plus "Chain verified, 10 entries"), then the timeline grouped by request under caps heads | each entry's hash, previous hash and disclosed fields |

## Our own pieces

These exist only where the kit has nothing that fits:
- `Facts`: halbat's facts line under a title.
- `OptionTable`: the ranked options as a halbat table (rank, product with id, amount, price, verdict). The kit has no table.
- `SpendBar`: the kit `Progress` with a tick at the auto limit, on a scale up to the hard cap.
- `Shell`: the kit sidebar wiring, the content bar, the phone header and the bottom bar.
- `ListRow`: the mail row recipe, copied value for value. The kit has no list-row primitive.
- `VerbRow`: the App-access and knowledge row (`verb / object / provenance / value`).
- `Drift`: the 8-week bar chart. The earlier weeks are fg 16 % and the two flagged weeks are fg primary, which is the system monitor's hot-cell logic in neutral ink. It has a dashed line at the usual value and 12px tabular labels, and no colour fill.

## Motion

Only the kit's tokens are used. Hover is a background shift at `--duration-fast`. Disclosure chevrons rotate 90° at micro. Nothing idles, and reduced motion turns all of it off.

## Checks before a page counts as done

- `npm run check` is clean and the e2e scenes are green.
- Screenshots at 1280 and 390 px are in `validio/artifacts/shots/` and have been looked at next to the Arlen renders and the website.
- `grep` over `src/` finds no `warn`, `caution`, `color-warning`, `theme-light`, and no raw hex outside `app.css`.
- The unslop checklist passes: no emoji, no gradient, no glow, nothing yellow, every colour has a meaning, and no copy line runs over 12 words.
- Then two review rounds with the same three reviewers.
