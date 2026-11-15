<script lang="ts">
  /// Search and commands, ⌘K (plans/013, 025 S4). A native <dialog>: focus stays inside, Escape
  /// closes. It opens and closes instantly, with no animation at all: people who use a palette
  /// open it many times a day.
  ///
  /// What it holds: what waits for the owner first (Review opens the item with the approval code
  /// already open), the last commands used, the places, the actions, and every activity item,
  /// searched by title and reason with the matching words marked.
  import { goto } from "$app/navigation";
  import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList, CommandShortcut } from "@arlen/ui-kit/components/ui/command";
  import { agentApi, type AgentState } from "$lib/api/agent";
  import { api } from "$lib/api/client";
  import type { ActivityItem } from "$lib/api/types";
  import { bump } from "$lib/chrome.svelte";
  import { session } from "$lib/owner.svelte";
  import { setMode } from "$lib/theme.svelte";
  import { toast } from "$lib/toast.svelte";
  import { money, pillOf } from "$lib/v2";
  import { highlight } from "./format";
  import { logOut } from "../../routes/settings/sections";

  let { onreset }: { onreset?: () => void } = $props();

  let dlg = $state<HTMLDialogElement>();
  let query = $state("");
  let items = $state<ActivityItem[]>([]);
  let agent = $state<AgentState | null>(null);
  let showKeys = $state(false);

  export function open(keys = false) {
    if (!dlg || dlg.open) return;
    query = "";
    showKeys = keys;
    dlg.showModal();
    // The search field takes the keys at once.
    queueMicrotask(() => dlg?.querySelector<HTMLInputElement>('[data-slot="command-input"]')?.focus());
    api.activity("all").then((l) => (items = l.items), () => {});
    agentApi.agent().then((a) => (agent = a), () => {});
  }
  function close() {
    dlg?.close();
  }

  interface Cmd {
    id: string;
    label: string;
    key?: string;
    run: () => unknown;
  }
  /** The last commands used, newest first, kept for this visit (plans/025, S4). */
  const used = (globalThis as { __validioUsed?: string[] }).__validioUsed ?? [];
  (globalThis as { __validioUsed?: string[] }).__validioUsed = used;
  async function run(c: Cmd) {
    const at = used.indexOf(c.id);
    if (at !== -1) used.splice(at, 1);
    used.unshift(c.id);
    used.length = Math.min(used.length, 3);
    close();
    await c.run();
  }

  const GO: Cmd[] = [
    { id: "go-home", label: "Home", key: "g h", run: () => goto("/") },
    { id: "go-activity", label: "Activity", key: "g a", run: () => goto("/activity") },
    { id: "go-waiting", label: "Waiting for you", key: "3", run: () => goto("/activity?status=waiting") },
    { id: "go-blocked", label: "Blocked", key: "4", run: () => goto("/activity?status=blocked") },
    { id: "go-rules", label: "Rules", key: "g r", run: () => goto("/rules") },
    { id: "go-edit", label: "Edit rules", run: () => goto("/rules/edit") },
    { id: "go-agent", label: "Agent", key: "g n", run: () => goto("/agent") },
    { id: "go-settings", label: "Settings", key: "g s", run: () => goto("/settings") },
  ];
  const pause = (paused: boolean) => async () => {
    await agentApi.pause(paused);
    bump();
    toast({
      tone: paused ? "wait" : "ok",
      title: paused ? "Agent paused" : "Agent resumed",
      body: paused ? "Every call is refused and logged" : "It orders within your Rules again",
      undo: async () => {
        await agentApi.pause(!paused);
        bump();
      },
    });
  };
  const actions = $derived.by((): Cmd[] => [
    ...(agent?.state === "active" ? [{ id: "agent-pause", label: "Pause agent", run: pause(true) }] : []),
    ...(agent?.state === "paused" ? [{ id: "agent-resume", label: "Resume agent", run: pause(false) }] : []),
    ...(agent?.state === "none" ? [{ id: "agent-connect", label: "Connect agent", run: () => goto("/agent") }] : []),
    ...(agent?.pairing?.mcpUrl
      ? [{ id: "agent-copy", label: "Copy the MCP address", run: () => navigator.clipboard.writeText(agent!.pairing!.mcpUrl).catch(() => {}) }]
      : []),
    { id: "theme-light", label: "Theme: Light", run: () => setMode("light") },
    { id: "theme-dark", label: "Theme: Dark", run: () => setMode("dark") },
    { id: "theme-system", label: "Theme: System", run: () => setMode("system") },
    ...(session.account?.isDemo && onreset ? [{ id: "demo-reset", label: "Start over", run: onreset }] : []),
    { id: "log-out", label: "Log out", run: logOut },
  ]);
  const all = $derived([...GO, ...actions]);
  const last = $derived(used.map((id) => all.find((c) => c.id === id)).filter((c): c is Cmd => !!c));

  const waiting = $derived(items.filter((i) => i.status === "waiting"));
  // With nothing typed: the newest eight. Typed: every item, the list filters them.
  const found = $derived(query.trim() ? items : items.slice(0, 8));
  const review = (i: ActivityItem): Cmd => ({
    id: `review-${i.id}`,
    label: `Review ${i.title}`,
    run: () => goto(`/activity/${encodeURIComponent(i.id)}?approve=1`),
  });

  const KEYS = [
    ["⌘K", "Search and commands"],
    ["g then h, a, r, n, s", "Home, Activity, Rules, Agent, Settings"],
    ["j, k", "Next or previous row"],
    ["Enter", "Open the row"],
    ["a", "Approve the waiting row"],
    ["/", "Find in Activity"],
    ["1 to 5", "Activity filters"],
    ["?", "These keys"],
  ];
</script>

{#snippet marked(text: string)}{#each highlight(text, query) as part, n (n)}{#if part.hit}<mark>{part.text}</mark>{:else}{part.text}{/if}{/each}{/snippet}

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_noninteractive_element_interactions (a click on the backdrop closes; Escape is the keyboard's way) -->
<dialog class="pal" bind:this={dlg} aria-label="Search and commands" data-testid="palette" onclick={(e) => e.target === dlg && close()}>
  <Command class="pal-cmd" loop>
    <CommandInput placeholder="Go to, find, or do" bind:value={query} />
    <CommandList class="pal-list">
      <CommandEmpty>Nothing matches "{query}"</CommandEmpty>
      {#if showKeys}
        <CommandGroup heading="Keys">
          {#each KEYS as [k, what] (k)}
            <CommandItem value="keys {what}" onSelect={close}><span class="pal-t">{what}</span><CommandShortcut>{k}</CommandShortcut></CommandItem>
          {/each}
        </CommandGroup>
      {/if}
      {#if waiting.length}
        <CommandGroup heading="Waiting for you">
          {#each waiting as i (i.id)}
            {@const c = review(i)}
            <CommandItem value="review approve {i.id} {i.title}" onSelect={() => run(c)} data-testid="pal-review-{i.id}">
              <span class="pal-t">Review <b>{@render marked(i.title)}</b></span>
              {#if i.totalCents != null}<span class="pal-m num">{money(i.totalCents)}</span>{/if}
            </CommandItem>
          {/each}
        </CommandGroup>
      {/if}
      {#if last.length && !query.trim()}
        <CommandGroup heading="Last used">
          {#each last as c (c.id)}
            <CommandItem value="last {c.label}" onSelect={() => run(c)}><span class="pal-t">{c.label}</span>{#if c.key}<CommandShortcut>{c.key}</CommandShortcut>{/if}</CommandItem>
          {/each}
        </CommandGroup>
      {/if}
      <CommandGroup heading="Go to">
        {#each GO as c (c.id)}
          <CommandItem value="go {c.label}" onSelect={() => run(c)}>
            <span class="pal-t">{@render marked(c.label)}</span>{#if c.key}<CommandShortcut>{c.key}</CommandShortcut>{/if}
          </CommandItem>
        {/each}
      </CommandGroup>
      <CommandGroup heading="Actions">
        {#each actions as c (c.id)}
          <CommandItem value="do {c.label}" onSelect={() => run(c)}><span class="pal-t">{@render marked(c.label)}</span></CommandItem>
        {/each}
        <CommandItem value="keys shortcuts help" onSelect={() => (showKeys = true)}><span class="pal-t">Show keys</span><CommandShortcut>?</CommandShortcut></CommandItem>
      </CommandGroup>
      {#if found.length}
        <CommandGroup heading={query.trim() ? "Activity" : "Recent"}>
          {#each found as i (i.id)}
            <CommandItem
              value="activity {i.id} {i.title} {i.why}"
              onSelect={() => run({ id: `open-${i.id}`, label: i.title, run: () => goto(`/activity/${encodeURIComponent(i.id)}`) })}
            >
              <span class="pal-t">{@render marked(i.title)}</span>
              <span class="pal-m tone-{pillOf(i).tone}-text">{pillOf(i).label}</span>
              {#if i.totalCents != null}<span class="pal-m num">{money(i.totalCents)}</span>{/if}
            </CommandItem>
          {/each}
        </CommandGroup>
      {/if}
    </CommandList>
    <div class="pal-foot" aria-hidden="true">
      <span><kbd>↑</kbd><kbd>↓</kbd> to move</span>
      <span><kbd>↵</kbd> to run</span>
      <span><kbd>esc</kbd> to close</span>
    </div>
  </Command>
</dialog>

<style>
  .pal {
    --color-fg-shell: var(--v-fg);
    width: min(600px, calc(100vw - 32px));
    max-height: min(520px, 72vh);
    margin: 12vh auto auto;
    padding: 0;
    border: 1px solid var(--v-line-strong);
    border-radius: var(--radius-modal);
    background: var(--v-surface);
    color: var(--v-fg);
    overflow: hidden;
  }
  .pal::backdrop {
    background: var(--v-tint-strong);
  }
  .pal :global(.pal-cmd) {
    background: var(--v-surface);
    border-radius: 0;
  }
  .pal :global([data-slot="command-input-wrapper"]) {
    min-height: 52px;
    gap: 10px;
    padding-inline: 16px;
    border-bottom-color: var(--v-line) !important;
  }
  .pal :global([data-slot="command-input-wrapper"] svg) {
    width: 18px;
    height: 18px;
  }
  /* One frame only: the dialog's. The field is the one place the keys can be, so it draws no ring
     of its own (the kit says the same about this input). */
  .pal :global([data-slot="command-input"]) {
    height: 52px;
    padding: 0;
    font-size: var(--fs-body);
    outline: none !important;
    box-shadow: none !important;
  }
  .pal :global(.pal-list) {
    max-height: min(400px, 56vh);
    padding: 6px;
  }
  .pal :global(.command-item-shell) {
    min-height: 38px;
    padding-inline: 10px;
    color: var(--v-fg);
    font-size: var(--fs-head);
    border-radius: var(--radius-button);
  }
  /* The pointer moves the selection, so there is one look: the chosen row, petrol on its tint
     with a petrol rule on the left. No second, softer hover look beside it. */
  .pal :global(.command-item-shell:hover) {
    background: transparent;
  }
  .pal :global(.command-item-shell[data-selected]) {
    background: var(--valio-tint) !important;
    color: var(--v-fg);
    box-shadow: inset 2px 0 0 var(--valio);
  }
  .pal :global([data-slot="command-group-heading"]) {
    padding: 10px 10px 4px;
    font-size: var(--fs-cap);
    color: var(--v-muted) !important;
  }
  .pal :global([data-slot="command-shortcut"]) {
    margin-left: auto;
    font-size: var(--fs-cap);
    color: var(--v-faint);
  }
  .pal :global([data-slot="command-empty"]) {
    padding: 24px 10px;
    font-size: var(--fs-head);
    color: var(--v-muted);
  }
  .pal-t {
    flex: 1 1 auto;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .pal-t b {
    font-weight: 500;
  }
  .pal-t :global(mark) {
    background: none;
    color: var(--valio);
    font-weight: 600;
  }
  .pal-m {
    flex: none;
    font-size: var(--fs-cap);
    color: var(--v-muted);
  }
  .pal-foot {
    display: flex;
    gap: 20px;
    padding: 9px 16px;
    border-top: 1px solid var(--v-line);
    font-size: var(--fs-cap);
    line-height: 16px;
    color: var(--v-faint);
  }
  .pal-foot kbd {
    display: inline-grid;
    place-items: center;
    min-width: 18px;
    height: 18px;
    margin-right: 3px;
    padding: 0 4px;
    border: 1px solid var(--v-line-strong);
    border-radius: var(--radius-chip);
    font-family: var(--v-sans);
    font-size: 11px;
    color: var(--v-muted);
  }
  @media (max-width: 760px) {
    .pal-foot {
      display: none;
    }
  }
</style>
