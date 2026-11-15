<script lang="ts">
  /// Search and commands, ⌘K (plans/013). A native <dialog>: focus stays inside, Escape closes.
  /// It opens and closes instantly, with no animation at all: people who use a palette open it
  /// many times a day.
  import { goto } from "$app/navigation";
  import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList, CommandShortcut } from "@arlen/ui-kit/components/ui/command";
  import { agentApi, type AgentState } from "$lib/api/agent";
  import { api } from "$lib/api/client";
  import type { ActivityItem } from "$lib/api/types";
  import { bump } from "$lib/chrome.svelte";
  import { session } from "$lib/owner.svelte";
  import { setMode } from "$lib/theme.svelte";
  import { money, pillOf } from "$lib/v2";
  import { logOut } from "../../routes/settings/sections";

  let { onreset }: { onreset?: () => void } = $props();

  let dlg = $state<HTMLDialogElement>();
  let query = $state("");
  let recent = $state<ActivityItem[]>([]);
  let agent = $state<AgentState | null>(null);
  let showKeys = $state(false);

  export function open(keys = false) {
    if (!dlg || dlg.open) return;
    query = "";
    showKeys = keys;
    dlg.showModal();
    // The search field takes the keys at once.
    queueMicrotask(() => dlg?.querySelector<HTMLInputElement>('[data-slot="command-input"]')?.focus());
    api.activity("all").then((l) => (recent = l.items.slice(0, 8)), () => {});
    agentApi.agent().then((a) => (agent = a), () => {});
  }
  function close() {
    dlg?.close();
  }
  async function run(fn: () => unknown) {
    close();
    await fn();
  }

  const GO = [
    { label: "Home", href: "/", key: "g h" },
    { label: "Activity", href: "/activity", key: "g a" },
    { label: "Waiting for you", href: "/activity?status=waiting", key: "3" },
    { label: "Blocked", href: "/activity?status=blocked", key: "4" },
    { label: "Rules", href: "/rules", key: "g r" },
    { label: "Edit rules", href: "/rules/edit" },
    { label: "Agent", href: "/agent", key: "g n" },
    { label: "Settings", href: "/settings", key: "g s" },
  ];
  const KEYS = [
    ["⌘K", "Search and commands"],
    ["g then h, a, r, n, s", "Home, Activity, Rules, Agent, Settings"],
    ["j, k", "Next or previous row"],
    ["1 to 5", "Activity filters"],
    ["?", "These keys"],
  ];
</script>

<dialog class="pal" bind:this={dlg} aria-label="Search and commands" onclick={(e) => e.target === dlg && close()}>
  <Command class="pal-cmd" loop>
    <CommandInput placeholder="Go to, find, or do" bind:value={query} />
    <CommandList class="pal-list">
      <CommandEmpty>Nothing matches</CommandEmpty>
      {#if showKeys}
        <CommandGroup heading="Keys">
          {#each KEYS as [k, what] (k)}
            <CommandItem value="keys {what}" onSelect={close}><span>{what}</span><CommandShortcut>{k}</CommandShortcut></CommandItem>
          {/each}
        </CommandGroup>
      {/if}
      <CommandGroup heading="Go to">
        {#each GO as g (g.href)}
          <CommandItem value="go {g.label}" onSelect={() => run(() => goto(g.href))}>
            <span>{g.label}</span>{#if g.key}<CommandShortcut>{g.key}</CommandShortcut>{/if}
          </CommandItem>
        {/each}
      </CommandGroup>
      {#if recent.length}
        <CommandGroup heading="Recent">
          {#each recent as i (i.id)}
            <CommandItem value="recent {i.id} {i.title} {i.why}" onSelect={() => run(() => goto(`/activity/${encodeURIComponent(i.id)}`))}>
              <span class="pal-t">{i.title}</span>
              <span class="pal-m tone-{pillOf(i).tone}-text">{pillOf(i).label}</span>
              {#if i.totalCents != null}<span class="pal-m num">{money(i.totalCents)}</span>{/if}
            </CommandItem>
          {/each}
        </CommandGroup>
      {/if}
      <CommandGroup heading="Actions">
        {#if agent?.state === "active"}
          <CommandItem value="pause agent" onSelect={() => run(async () => (await agentApi.pause(true), bump()))}>Pause agent</CommandItem>
        {:else if agent?.state === "paused"}
          <CommandItem value="resume agent" onSelect={() => run(async () => (await agentApi.pause(false), bump()))}>Resume agent</CommandItem>
        {:else if agent?.state === "none"}
          <CommandItem value="connect agent" onSelect={() => run(() => goto("/agent"))}>Connect agent</CommandItem>
        {/if}
        <CommandItem value="theme light" onSelect={() => run(() => setMode("light"))}>Theme: Light</CommandItem>
        <CommandItem value="theme dark" onSelect={() => run(() => setMode("dark"))}>Theme: Dark</CommandItem>
        <CommandItem value="theme system" onSelect={() => run(() => setMode("system"))}>Theme: System</CommandItem>
        {#if session.account?.isDemo && onreset}
          <CommandItem value="start over demo" onSelect={() => run(onreset)}>Start over</CommandItem>
        {/if}
        <CommandItem value="log out" onSelect={() => run(logOut)}>Log out</CommandItem>
        <CommandItem value="keys shortcuts help" onSelect={() => (showKeys = true)}>Show keys<CommandShortcut>?</CommandShortcut></CommandItem>
      </CommandGroup>
    </CommandList>
  </Command>
</dialog>

<style>
  .pal {
    --color-fg-shell: var(--v-fg);
    width: min(560px, calc(100vw - 32px));
    max-height: min(480px, 70vh);
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
    min-height: 48px;
    border-bottom-color: var(--v-line) !important;
  }
  .pal :global([data-slot="command-input"]) {
    font-size: var(--fs-body);
  }
  .pal :global(.pal-list) {
    max-height: min(420px, 60vh);
    padding: 4px;
  }
  .pal :global(.command-item-shell) {
    color: var(--v-fg);
    font-size: var(--fs-head);
  }
  .pal :global(.command-item-shell:hover) {
    background: var(--v-tint-hover);
  }
  .pal :global(.command-item-shell[data-selected]) {
    background: var(--valio-tint) !important;
    color: var(--v-fg);
  }
  .pal :global([data-slot="command-group-heading"]) {
    color: var(--v-muted) !important;
  }
  .pal :global([data-slot="command-shortcut"]) {
    margin-left: auto;
    font-size: var(--fs-cap);
    color: var(--v-faint);
  }
  .pal-t {
    flex: 1 1 auto;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .pal-m {
    flex: none;
    font-size: var(--fs-cap);
    color: var(--v-muted);
  }
</style>
