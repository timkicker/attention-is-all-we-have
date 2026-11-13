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
  import { IconAction } from "@arlen/ui-kit/components/ui/icon-action";
  import { Badge } from "@arlen/ui-kit/components/ui/badge";
  import * as DropdownMenu from "@arlen/ui-kit/components/ui/dropdown-menu";
  import { CalendarSync, Check, ChevronLeft, Ellipsis, FlaskConical, Inbox, KeyRound, RotateCcw, ScrollText, ShieldCheck } from "@lucide/svelte";
  import { ApiError, api, LIVE } from "$lib/api/client";
  import { owner } from "$lib/owner.svelte";
  import { CLOCK, dayTime } from "$lib/format";
  import { poll } from "$lib/poll";
  import { bump, chrome, demoActions } from "$lib/chrome.svelte";

  let { children } = $props();

  const NAV = [
    { href: "/", id: "nav-inbox", label: "Inbox", short: "Inbox", icon: Inbox, match: (p: string) => p === "/" || p.startsWith("/requests") },
    { href: "/steady", id: "nav-steady-orders", label: "Steady orders", short: "Steady", icon: CalendarSync, match: (p: string) => p.startsWith("/steady") },
    { href: "/ledger", id: "nav-open-ledger", label: "Ledger", short: "Ledger", icon: ScrollText, match: (p: string) => p.startsWith("/ledger") },
  ];
  const PASS = { href: "/spend-pass", id: "nav-spend-pass", label: "Spend Pass", short: "Pass", icon: ShieldCheck, match: (p: string) => p.startsWith("/spend-pass") };

  const path = $derived(page.url.pathname);
  // The approve page is one question and two buttons: no dock under it.
  const single = $derived(path.startsWith("/approve"));

  onMount(() => {
    const q = window.matchMedia("(max-width: 760px)");
    const set = () => (chrome.phone = q.matches);
    set();
    q.addEventListener("change", set);
    return () => q.removeEventListener("change", set);
  });

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
  demoActions.stockOut = stockOut;
  // Whether the stock-out is on, for the check mark in the menu.
  let stockIsOut = $state(false);
  $effect(() => {
    void chrome.version;
    api.demoState().then((d) => (stockIsOut = d.stockOut466375), () => {});
  });
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
  {#if !chrome.phone}
  <Sidebar collapsible="icon">
    <SidebarHeader>
      <div class="brand"><span class="brand-name">Validio</span></div>
    </SidebarHeader>
    <SidebarContent>
      <nav aria-label="Main">
        <SidebarGroup>
          <SidebarMenu>
            {#each NAV as item (item.href)}
              <SidebarMenuItem>
                <SidebarMenuButton id={item.id} data-testid={item.id} isActive={item.match(path)} tooltip={item.label} onclick={() => goto(item.href)}>
                  <item.icon strokeWidth={1.75} />
                  <span>{item.label}</span>
                  {#if item.href === "/" && waiting > 0}
                    <span class="count"><Badge variant="secondary" aria-label="{waiting} waiting for you">{waiting}</Badge></span>
                  {/if}
                </SidebarMenuButton>
              </SidebarMenuItem>
            {/each}
          </SidebarMenu>
        </SidebarGroup>
        <SidebarGroup>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton id={PASS.id} data-testid={PASS.id} isActive={PASS.match(path)} tooltip={PASS.label} onclick={() => goto(PASS.href)}>
                <PASS.icon strokeWidth={1.75} />
                <span>{PASS.label}</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarGroup>
      </nav>
    </SidebarContent>
    <SidebarFooter>
      <div class="kitchen">
        <span class="kitchen-name">Hotel Espoo kitchen</span>
        <span class="clock num">{dayTime(CLOCK)}</span>
      </div>
    </SidebarFooter>
    <SidebarRail />
  </Sidebar>
  {/if}

  <SidebarInset class="inset">
    <h1 class="sr-only">Validio</h1>
    <header class="bar">
      {#if !chrome.phone}
        <SidebarTrigger class="-ml-1" />
        <Separator orientation="vertical" class="me-1 h-4!" />
      {/if}
      {#if chrome.back && chrome.phone}
        {@const to = chrome.back.href}
        <IconAction size="control" label="Back to {chrome.back.label}" onclick={() => goto(to)}>
          <ChevronLeft size={18} strokeWidth={1.75} />
        </IconAction>
      {/if}
      <!-- On the phone a detail page names its parent here and the thing in its
           own heading, so the title is said once. -->
      <span class="bar-title" id="bar-title">{chrome.phone && chrome.back ? chrome.back.label : chrome.title}</span>
      <span class="grow"></span>
      <DropdownMenu.Root>
        <DropdownMenu.Trigger>
          {#snippet child({ props })}
            <!-- The tooltip trigger sets its own id on the button, so the
                 stable id the suites and the video click sits on this span. -->
            <span class="menu-wrap" id="page-menu">
              <Button {...props} variant="ghost" size="icon-sm" tooltip="Demo controls" aria-label="Demo controls" data-testid="page-menu" class="menu-btn">
                <Ellipsis />
              </Button>
            </span>
          {/snippet}
        </DropdownMenu.Trigger>
        <DropdownMenu.Content align="end">
          <DropdownMenu.Label>Demo controls</DropdownMenu.Label>
          {#if !LIVE}<p class="menu-note" id="demo-data">Example orders, not this kitchen's.</p>{/if}
          <DropdownMenu.Item
            id="stock-out"
            data-testid="stock-out"
            disabled={stockIsOut}
            aria-label={stockIsOut ? "Stock-out of 466375 simulated" : "Simulate stock-out of 466375"}
            onSelect={stockOut}
          >
            {#if stockIsOut}<Check size={15} strokeWidth={1.75} />{:else}<FlaskConical size={15} strokeWidth={1.75} />{/if}
            {stockIsOut ? "Stock-out of 466375 simulated" : "Simulate stock-out of 466375"}
          </DropdownMenu.Item>
          <DropdownMenu.Item id="menu-reset" onSelect={reset}>
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
  <nav class="dock" aria-label="Main, phone">
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
  .brand {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    min-height: 1.5rem;
    padding-inline: 0.25rem;
    overflow: hidden;
  }
  .brand-name {
    font-size: var(--text-md);
    font-weight: 600;
    white-space: nowrap;
  }
  .kitchen {
    display: flex;
    flex-direction: column;
    padding: 0.25rem 0.5rem;
    white-space: nowrap;
    overflow: hidden;
  }
  .kitchen-name {
    font-size: var(--text-sm);
    font-weight: 500;
  }
  .clock {
    font-size: var(--text-2xs);
    color: var(--color-fg-secondary);
  }
  :global([data-collapsible="icon"]) :is(.kitchen, .brand-name, .count) {
    display: none;
  }
  .count {
    margin-inline-start: auto;
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
  .menu-wrap {
    display: inline-flex;
  }
  .menu-note {
    margin: 0;
    padding: 0 0.5rem 0.35rem;
    font-size: var(--text-xs);
    color: var(--color-fg-secondary);
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
    .bar {
      min-height: 3rem;
      padding-inline: 0.5rem;
    }
    .bar-title {
      font-size: var(--text-md);
      font-weight: 600;
      padding-inline-start: 0.5rem;
    }
    .bar :global(.menu-btn) {
      width: 2.75rem;
      height: 2.75rem;
    }
    /* On the phone the page itself scrolls, not a box inside it. */
    :global(.app),
    :global(.inset) {
      height: auto;
      min-height: 100svh;
      overflow: visible;
    }
    .bar {
      position: sticky;
      top: 0;
      z-index: 15;
    }
    .content {
      overflow: visible;
      padding-bottom: calc(6rem + env(safe-area-inset-bottom));
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
      /* Dark carries elevation in surface lightness; light lifts the card. */
      box-shadow: var(--shadow-card, none);
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
