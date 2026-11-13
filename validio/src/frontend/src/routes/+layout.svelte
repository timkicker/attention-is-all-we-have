<script lang="ts">
  import "../app.css";
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { page } from "$app/state";
  import {
    Sidebar,
    SidebarContent,
    SidebarFooter,
    SidebarGroup,
    SidebarGroupLabel,
    SidebarHeader,
    SidebarInset,
    SidebarMenu,
    SidebarMenuButton,
    SidebarMenuItem,
    SidebarProvider,
    SidebarRail,
    SidebarTrigger,
  } from "@arlen/ui-kit/components/ui/sidebar";
  import { Separator } from "@arlen/ui-kit/components/ui/separator";
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import { Dialog } from "@arlen/ui-kit/components/ui/dialog";
  import { Input } from "@arlen/ui-kit/components/ui/input";
  import * as DropdownMenu from "@arlen/ui-kit/components/ui/dropdown-menu";
  import { CalendarSync, ChevronLeft, Ellipsis, Inbox, KeyRound, RotateCcw, ScrollText, ShieldCheck, PackageX } from "@lucide/svelte";
  import { ApiError, api, LIVE } from "$lib/api/client";
  import { owner } from "$lib/owner.svelte";
  import { CLOCK, dayTime } from "$lib/format";
  import { poll } from "$lib/poll";
  import { bump, chrome } from "$lib/chrome.svelte";

  let { children } = $props();

  const NAV = [
    { href: "/", id: "nav-inbox", label: "Inbox", short: "Inbox", icon: Inbox, match: (p: string) => p === "/" || p.startsWith("/requests") },
    { href: "/steady", id: "nav-steady-orders", label: "Steady orders", short: "Steady", icon: CalendarSync, match: (p: string) => p.startsWith("/steady") },
    { href: "/ledger", id: "nav-open-ledger", label: "Open ledger", short: "Ledger", icon: ScrollText, match: (p: string) => p.startsWith("/ledger") },
  ];
  const PASS = { href: "/spend-pass", id: "nav-spend-pass", label: "Spend Pass", short: "Pass", icon: ShieldCheck, match: (p: string) => p.startsWith("/spend-pass") };

  const path = $derived(page.url.pathname);
  // The approve page is one question and two buttons: no dock under it.
  const single = $derived(path.startsWith("/approve"));

  let waiting = $state(0);
  onMount(() =>
    poll(async () => {
      const items = await api.inbox();
      waiting = items.filter((i) => i.status === "waiting").length;
    }),
  );
  // Refresh the count at once after a demo action.
  $effect(() => {
    void chrome.version;
    api.inbox().then((items) => (waiting = items.filter((i) => i.status === "waiting").length));
  });

  // A demo switch the server refused for want of the token opens the token
  // dialog and runs again once the presenter typed it.
  let tokenOpen = $state(false);
  let tokenValue = $state("");
  let then = $state<null | (() => void)>(null);
  let demoProblem = $state("");

  async function demo(fn: () => Promise<unknown>, next: string) {
    demoProblem = "";
    try {
      await fn();
      bump();
      goto(next);
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) {
        then = () => demo(fn, next);
        tokenValue = "";
        demoProblem = owner.demoToken ? "That token is not right." : "";
        tokenOpen = true;
      } else {
        demoProblem = e instanceof Error ? e.message : String(e);
        then = null;
        tokenOpen = true;
      }
    }
  }
  // The fixture answers at once; with the backend the kitchen's agent asks again first.
  const stockOut = () => demo(() => api.stockOut(), LIVE ? "/" : "/requests/R-2");
  const reset = () => demo(() => api.reset(), "/");
  function useToken(e: SubmitEvent) {
    e.preventDefault();
    owner.demoToken = tokenValue.trim();
    tokenOpen = false;
    const run = then;
    then = null;
    run?.();
  }
</script>

<svelte:head>
  <title>{chrome.title ? `${chrome.title}, Validio` : "Validio"}</title>
</svelte:head>

<SidebarProvider class="app">
  <Sidebar collapsible="icon">
    <SidebarHeader>
      <div class="kitchen">
        <span class="tile" aria-hidden="true">H</span>
        <span class="kitchen-name">Hotel Espoo kitchen</span>
      </div>
    </SidebarHeader>
    <SidebarContent>
      <nav aria-label="Main">
        <SidebarGroup>
          <SidebarMenu>
            {#each NAV as item (item.href)}
              <SidebarMenuItem>
                <SidebarMenuButton id={item.id} isActive={item.match(path)} tooltip={item.label} onclick={() => goto(item.href)}>
                  <item.icon strokeWidth={1.75} />
                  <span>{item.label}</span>
                  {#if item.href === "/" && waiting > 0}
                    <span class="count num" aria-label="{waiting} waiting">{waiting}</span>
                  {/if}
                </SidebarMenuButton>
              </SidebarMenuItem>
            {/each}
          </SidebarMenu>
        </SidebarGroup>
        <SidebarGroup>
          <SidebarGroupLabel>Authority</SidebarGroupLabel>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton id={PASS.id} isActive={PASS.match(path)} tooltip={PASS.label} onclick={() => goto(PASS.href)}>
                <PASS.icon strokeWidth={1.75} />
                <span>{PASS.label}</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarGroup>
      </nav>
    </SidebarContent>
    <SidebarFooter>
      <p class="clock num">{dayTime(CLOCK)}</p>
    </SidebarFooter>
    <SidebarRail />
  </Sidebar>

  <SidebarInset class="inset">
    <h1 class="sr-only">Validio</h1>
    <header class="bar">
      <span class="desk"><SidebarTrigger class="-ml-1" /></span>
      <span class="desk"><Separator orientation="vertical" class="me-1 h-4!" /></span>
      {#if chrome.back}
        <a class="back" href={chrome.back.href} aria-label="Back to {chrome.back.label}">
          <ChevronLeft size={20} strokeWidth={1.75} />
        </a>
      {/if}
      <span class="bar-title" id="bar-title">{chrome.title}</span>
      <span class="grow"></span>
      <DropdownMenu.Root>
        <DropdownMenu.Trigger>
          {#snippet child({ props })}
            <button {...props} type="button" class="menu-btn" id="page-menu" aria-label="Demo controls">
              <Ellipsis size={16} strokeWidth={1.75} />
            </button>
          {/snippet}
        </DropdownMenu.Trigger>
        <DropdownMenu.Content align="end" class="w-56">
          <DropdownMenu.Label>Demo controls</DropdownMenu.Label>
          <DropdownMenu.Item id="stock-out" onSelect={stockOut}>
            <PackageX size={15} strokeWidth={1.75} />
            Simulate stock-out
          </DropdownMenu.Item>
          <DropdownMenu.Item id="reset" onSelect={reset}>
            <RotateCcw size={15} strokeWidth={1.75} />
            Start over
          </DropdownMenu.Item>
          {#if LIVE}
            <DropdownMenu.Separator />
            <DropdownMenu.Item id="demo-token" onSelect={() => { then = null; demoProblem = ""; tokenValue = owner.demoToken; tokenOpen = true; }}>
              <KeyRound size={15} strokeWidth={1.75} />
              Demo token
            </DropdownMenu.Item>
          {/if}
        </DropdownMenu.Content>
      </DropdownMenu.Root>
    </header>
    <main class="content" class:single>
      {@render children()}
    </main>
  </SidebarInset>
</SidebarProvider>

<Dialog open={tokenOpen} onClose={() => (tokenOpen = false)} labelledby="token-title" size="sm">
  <form class="token" onsubmit={useToken}>
    <h2 id="token-title">{then || !demoProblem ? "Demo token" : "Demo control failed"}</h2>
    {#if then || !demoProblem}
      <label for="demo-token-input">The presenter's token. Kept until you close the page.</label>
      <Input id="demo-token-input" bind:value={tokenValue} autocomplete="off" aria-invalid={demoProblem ? true : undefined} />
    {/if}
    {#if demoProblem}<p class="t-bad">{demoProblem}</p>{/if}
    <div class="token-buttons">
      <Button variant="outline" onclick={() => (tokenOpen = false)}>Cancel</Button>
      {#if then || !demoProblem}<Button type="submit">{then ? "Use and run" : "Use"}</Button>{/if}
    </div>
  </form>
</Dialog>

{#if !single}
  <nav class="dock shadow-lg" aria-label="Main, phone">
    {#each [...NAV, PASS] as item (item.href)}
      <a href={item.href} class:on={item.match(path)} aria-current={item.match(path) ? "page" : undefined}>
        <span class="pw"><item.icon size={20} strokeWidth={1.75} /></span>
        <span>{item.short}</span>
      </a>
    {/each}
  </nav>
{/if}

<style>
  :global(.app) {
    height: 100svh;
    min-height: 0;
    overflow: hidden;
  }
  :global(.inset) {
    height: 100svh;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }
  .kitchen {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    min-height: 1.5rem;
    padding-inline: 0.25rem;
    overflow: hidden;
  }
  .tile {
    display: grid;
    place-items: center;
    flex-shrink: 0;
    width: 1.5rem;
    height: 1.5rem;
    border-radius: var(--radius-button);
    background: color-mix(in srgb, var(--color-fg-primary) 10%, transparent);
    font-size: var(--text-xs);
    font-weight: 600;
  }
  .kitchen-name {
    font-size: var(--text-sm);
    font-weight: 500;
    white-space: nowrap;
  }
  :global([data-collapsible="icon"]) .kitchen-name,
  :global([data-collapsible="icon"]) .clock {
    display: none;
  }
  .count {
    margin-inline-start: auto;
    font-size: var(--text-xs);
    color: color-mix(in srgb, var(--sidebar-foreground) 55%, transparent);
  }
  :global([data-collapsible="icon"]) .count {
    display: none;
  }
  /* One selection, one mark: a steel line at the left edge, no fill. */
  :global([data-sidebar="menu-button"]) {
    position: relative;
    overflow: visible !important;
  }
  :global([data-sidebar="menu-button"][data-active="true"]) {
    background: transparent;
  }
  :global([data-sidebar="menu-button"][data-active="true"]:hover) {
    background: var(--sidebar-accent);
  }
  :global([data-sidebar="menu-button"][data-active="true"])::before {
    content: "";
    position: absolute;
    inset-inline-start: -0.5rem;
    top: 0.375rem;
    bottom: 0.375rem;
    width: 2px;
    background: var(--v-select);
  }
  .clock {
    padding-inline: 0.5rem;
    font-size: var(--text-2xs);
    color: var(--color-fg-secondary);
  }

  .bar {
    display: flex;
    flex-shrink: 0;
    align-items: center;
    gap: 0.5rem;
    min-height: 2.5rem;
    padding-inline: 0.5rem;
    border-bottom: 1px solid var(--color-border);
    background: var(--background);
  }
  .desk {
    display: inline-flex;
    align-items: center;
  }
  .bar-title {
    min-width: 10ch;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: var(--text-sm);
    font-weight: 500;
  }
  .grow {
    flex: 1;
  }
  .menu-btn,
  .back {
    display: inline-grid;
    place-items: center;
    width: 1.75rem;
    height: 1.75rem;
    border-radius: var(--radius-input);
    color: var(--color-fg-secondary);
    transition: background-color var(--duration-fast) var(--ease-default);
  }
  .menu-btn:hover,
  .back:hover {
    background: color-mix(in srgb, var(--color-fg-primary) 8%, transparent);
    color: var(--color-fg-primary);
  }
  .back {
    display: none;
  }
  .token {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    padding: 1.5rem;
  }
  .token h2 {
    margin: 0;
    font-size: var(--text-base);
    font-weight: 600;
  }
  .token label,
  .token p {
    margin: 0;
    font-size: var(--text-sm);
    color: var(--color-fg-secondary);
  }
  .token p.t-bad {
    color: var(--destructive-on-tint);
  }
  .token-buttons {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.5rem;
    margin-top: 0.5rem;
  }
  .content {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
  }

  .dock {
    display: none;
  }

  @media (max-width: 760px) {
    :global([data-slot="sidebar"]) {
      display: none !important;
    }
    .desk {
      display: none;
    }
    .bar {
      min-height: 3rem;
      padding-inline: 0.5rem;
    }
    .bar-title {
      font-size: var(--text-md);
      font-weight: 600;
      padding-inline-start: 0.5rem;
    }
    .back {
      display: inline-grid;
      width: 2.75rem;
      height: 2.75rem;
    }
    .back + .bar-title {
      padding-inline-start: 0;
    }
    .menu-btn {
      width: 2.75rem;
      height: 2.75rem;
    }
    .content {
      padding-bottom: calc(6rem + env(safe-area-inset-bottom));
    }
    .content.single {
      padding-bottom: 0;
    }
    .dock {
      position: fixed;
      inset-inline: 0.75rem;
      bottom: calc(0.75rem + env(safe-area-inset-bottom));
      z-index: 20;
      display: grid;
      grid-auto-flow: column;
      grid-auto-columns: 1fr;
      align-items: center;
      height: 4rem;
      border: 1px solid var(--color-border);
      border-radius: var(--radius-card);
      background: var(--color-bg-card);
    }
    .dock a {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 0.25rem;
      height: 100%;
      font-size: var(--text-2xs);
      font-weight: 500;
      color: var(--color-fg-secondary);
    }
    .dock a.on {
      color: var(--color-fg-primary);
    }
    .pw {
      display: grid;
      place-items: center;
      width: 3.25rem;
      height: 1.75rem;
      border-radius: var(--radius-button);
    }
    .dock a.on .pw {
      background: color-mix(in srgb, var(--color-fg-primary) 12%, transparent);
    }
  }
</style>
