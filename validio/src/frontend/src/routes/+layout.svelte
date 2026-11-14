<script lang="ts">
  import "../app.css";
  import { onMount } from "svelte";
  import { afterNavigate, goto } from "$app/navigation";
  import { page } from "$app/state";
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import { Dialog } from "@arlen/ui-kit/components/ui/dialog";
  import { Input } from "@arlen/ui-kit/components/ui/input";
  import * as Tooltip from "@arlen/ui-kit/components/ui/tooltip";
  import { notePage } from "@arlen/ui-kit/components/ui/page/history";
  import { Activity, Bot, ChevronRight, House, PanelLeft, ShieldCheck } from "@lucide/svelte";
  import { api, LIVE, needsToken } from "$lib/api/client";
  import { tokenPrompt } from "$lib/api/error";
  import { owner, session } from "$lib/owner.svelte";
  import { poll } from "$lib/poll";
  import { bump, chrome } from "$lib/chrome.svelte";
  import VPill from "$lib/v/VPill.svelte";

  let { children } = $props();

  // Four places, flat. The kitchen's name at the foot (top on the phone) opens Settings.
  const PAGES = [
    { href: "/", id: "nav-home", label: "Home", icon: House, match: (p: string) => p === "/" },
    { href: "/activity", id: "nav-activity", label: "Activity", icon: Activity, match: (p: string) => p.startsWith("/activity") },
    { href: "/rules", id: "nav-rules", label: "Rules", icon: ShieldCheck, match: (p: string) => p.startsWith("/rules") },
    { href: "/agent", id: "nav-agent", label: "Agent", icon: Bot, match: (p: string) => p.startsWith("/agent") },
  ];

  const path = $derived(page.url.pathname);
  // The login page stands alone: no sidebar, no tab bar.
  const door = $derived(path === "/login");

  // Who is logged in, once; a 401 later (api/client.ts) clears it again.
  onMount(() => {
    api.account().then(
      (a) => (session.account = a),
      () => (session.account = null),
    ).finally(() => (session.checked = true));
  });
  $effect(() => {
    if (!session.checked) return;
    if (!session.account && !door) void goto("/login", { replaceState: true });
    else if (session.account && door) void goto("/", { replaceState: true });
  });
  // The thin bar, on demo kitchens only.
  const demoBar = $derived(!!session.account?.isDemo);

  afterNavigate(({ to }) => {
    if (to?.url) notePage(to.url.pathname);
  });

  // The rail: the window between phone and desktop, or the person folded it.
  let folded = $state(false);
  let mid = $state(false);
  onMount(() => {
    const q = window.matchMedia("(min-width: 761px) and (max-width: 1023px)");
    const set = () => (mid = q.matches);
    set();
    q.addEventListener("change", set);
    return () => q.removeEventListener("change", set);
  });
  const rail = $derived(folded || mid);

  // What waits for the owner, on Home's nav item.
  let waiting = $state(0);
  const count = async () => {
    if (!session.account) return;
    waiting = (await api.home()).needsYou.length;
  };
  onMount(() => poll(count));
  $effect(() => {
    void chrome.version;
    if (session.account) count().catch(() => {});
  });

  // A demo Reset the server refused for want of the token (the public link)
  // opens the token dialog; the client sends it again once it is typed (api/client.ts, gated).
  let tokenOpen = $state(false);
  let tokenValue = $state("");
  let then = $state<null | (() => void)>(null);
  let demoProblem = $state("");
  let answerToken: null | ((ok: boolean) => void) = null;
  tokenPrompt.ask = () =>
    new Promise<boolean>((resolve) => {
      answerToken?.(false);
      answerToken = resolve;
      // A wrong token stays in the field, so it can be corrected.
      tokenValue = owner.demoToken;
      demoProblem = owner.demoToken ? "That token is not right." : "";
      then = () => {
        answerToken = null;
        resolve(true);
      };
      tokenOpen = true;
    });
  function closeToken() {
    tokenOpen = false;
    then = null;
    answerToken?.(false);
    answerToken = null;
  }

  async function reset() {
    demoProblem = "";
    try {
      await api.reset();
      bump();
      await goto("/");
    } catch (e) {
      if (needsToken(e)) return; // the token dialog was closed
      demoProblem = e instanceof Error ? e.message : String(e);
      then = null;
      tokenOpen = true;
    }
  }

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

{#snippet navBadge(n: number)}
  <span class="nb"><VPill count label={String(n)} tone="wait" /></span>
  <span class="sr-only">, {n} waiting</span>
{/snippet}

{#if door}
  <main class="v-main">
    <div class="wrap">{@render children()}</div>
  </main>
{:else if session.account}
{#if demoBar}
  <div class="demobar" data-testid="demo-bar" id="demo-bar">
    <span class="db-name">Demo kitchen</span>
    <Button variant="ghost" size="sm" class="hit" id="demo-reset" data-testid="demo-reset" onclick={reset}>Reset</Button>
  </div>
{/if}
<div class="shell" class:rail class:phone={chrome.phone}>
  {#if !chrome.phone}
    <aside class="side">
      <div class="top">
        <span class="brand">Validio</span>
        {#if !mid}
          <Button variant="ghost" size="icon-sm" class="fold" id="nav-fold" aria-label={folded ? "Open the sidebar" : "Fold the sidebar"} aria-pressed={folded} onclick={() => (folded = !folded)}>
            <PanelLeft />
          </Button>
        {/if}
      </div>
      <nav aria-label="Main">
        {#each PAGES as p (p.href)}
          {#if rail}
            <Tooltip.Root>
              <Tooltip.Trigger>
                {#snippet child({ props })}
                  <a {...props} href={p.href} id={p.id} data-testid={p.id} class="nav" class:on={p.match(path)} aria-current={p.match(path) ? "page" : undefined}>
                    <p.icon size={16} strokeWidth={1.75} aria-hidden="true" /><span class="sr-only">{p.label}</span>
                    {#if p.href === "/" && waiting > 0}{@render navBadge(waiting)}{/if}
                  </a>
                {/snippet}
              </Tooltip.Trigger>
              <Tooltip.TooltipContent side="right">{p.label}</Tooltip.TooltipContent>
            </Tooltip.Root>
          {:else}
            <a href={p.href} id={p.id} data-testid={p.id} class="nav" class:on={p.match(path)} aria-current={p.match(path) ? "page" : undefined}>
              <p.icon size={16} strokeWidth={1.75} aria-hidden="true" /><span class="lbl">{p.label}</span>
              {#if p.href === "/" && waiting > 0}{@render navBadge(waiting)}{/if}
            </a>
          {/if}
        {/each}
      </nav>
      <a class="nav foot" href="/settings" id="nav-settings" data-testid="nav-settings" class:on={path.startsWith("/settings")} aria-current={path.startsWith("/settings") ? "page" : undefined}>
        <span class="tile" aria-hidden="true">{session.account.name.charAt(0)}</span>
        <span class="lbl kitchen">{session.account.name}</span>
        <span class="sr-only">, Settings</span>
        <ChevronRight class="lbl foot-go" size={16} strokeWidth={1.75} aria-hidden="true" />
      </a>
    </aside>
  {/if}

  <main class="v-main">
    {#if chrome.phone && !chrome.detail}
      <header class="phonebar">
        <a class="pb-name" href="/settings" id="phone-settings" data-testid="phone-settings">
          <span class="tile" aria-hidden="true">{session.account.name.charAt(0)}</span>
          <span>{session.account.name}</span>
          <span class="sr-only">, Settings</span>
        </a>
        <ChevronRight class="pb-go" size={16} strokeWidth={1.75} aria-hidden="true" />
      </header>
    {/if}
    <div class="wrap">
      {@render children()}
    </div>
  </main>
</div>

{/if}

{#if session.account && !door && chrome.phone}
  <nav class="dock" aria-label="Main">
    {#each PAGES as p (p.href)}
      <a href={p.href} id="{p.id}-tab" data-testid="{p.id}-tab" class:on={p.match(path)} aria-current={p.match(path) ? "page" : undefined}>
        <span class="di"><p.icon size={20} strokeWidth={1.75} aria-hidden="true" />{#if p.href === "/" && waiting > 0}<span class="db">{@render navBadge(waiting)}</span>{/if}</span>
        <span>{p.label}</span>
      </a>
    {/each}
  </nav>
{/if}

<Dialog open={tokenOpen} onClose={closeToken} labelledby="token-title" size="sm">
  <form class="token" onsubmit={useToken}>
    {#if then || !demoProblem}
      <h2 id="token-title"><label for="demo-token-input">Demo token</label></h2>
      <Input
        id="demo-token-input"
        bind:value={tokenValue}
        autocomplete="off"
        aria-invalid={demoProblem ? true : undefined}
        aria-describedby={demoProblem ? "token-problem" : undefined}
      />
    {:else}
      <h2 id="token-title">Reset failed</h2>
    {/if}
    {#if demoProblem}<p class="bad" id="token-problem" data-testid="token-problem">{demoProblem}</p>{/if}
    <div class="token-buttons">
      <Button variant="ghost" id="token-cancel" onclick={closeToken}>{then || !demoProblem ? "Cancel" : "Close"}</Button>
      {#if then || !demoProblem}<Button type="submit" id="token-run" data-testid="token-run">Run</Button>{/if}
    </div>
  </form>
</Dialog>

{#if LIVE}<span hidden id="live-mode"></span>{/if}

<style>
  /* The demo bar's height, for everything that sticks under it. */
  :global(:root) {
    --demo-h: 0px;
  }
  :global(:root:has(#demo-bar)) {
    --demo-h: 32px;
  }
  .shell {
    position: relative;
    display: grid;
    grid-template-columns: 232px minmax(0, 1fr);
    min-height: 100vh;
  }
  /* The sidebar's colour runs the whole page height, also past the sticky panel. */
  .shell:not(.phone)::before {
    content: "";
    position: absolute;
    inset: 0 auto 0 0;
    width: 232px;
    background: var(--v-shell);
    border-right: 1px solid var(--v-line);
  }
  .shell.rail::before {
    width: 48px;
  }
  .shell.rail {
    grid-template-columns: 48px minmax(0, 1fr);
  }
  .shell.phone {
    grid-template-columns: minmax(0, 1fr);
  }
  .v-main {
    min-width: 0;
  }
  .side {
    position: sticky;
    top: var(--demo-h);
    height: calc(100vh - var(--demo-h));
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 8px;
    background: var(--v-shell);
    border-right: 1px solid var(--v-line);
    z-index: 5;
  }
  .top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 32px;
    padding-left: 8px;
    margin-bottom: 8px;
  }
  .brand {
    font-size: 15px;
    line-height: 22px;
    font-weight: 600;
  }
  .side nav {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .nav {
    position: relative;
    display: flex;
    align-items: center;
    gap: 12px;
    height: 32px;
    padding: 0 8px;
    border-radius: var(--radius-button);
    font-size: 13px;
    line-height: 20px;
    color: var(--v-muted);
    white-space: nowrap;
    text-decoration: none;
  }
  .nav :global(svg) {
    flex: none;
    color: var(--v-faint);
  }
  .nav.on :global(svg) {
    color: var(--v-fg);
  }
  a.nav:hover:not(.on) {
    background: var(--v-tint-hover);
    color: var(--v-fg);
  }
  .nav.on {
    color: var(--v-fg);
    font-weight: 500;
  }
  .nav.on::before {
    content: "";
    position: absolute;
    left: -8px;
    top: 8px;
    bottom: 8px;
    width: 2px;
    background: var(--valio);
  }
  .nb {
    margin-left: auto;
    display: inline-flex;
  }
  .foot {
    margin-top: auto;
    height: 40px;
    overflow: hidden;
  }
  .foot :global(.foot-go) {
    margin-left: auto;
  }
  .tile {
    display: inline-grid;
    place-items: center;
    flex: none;
    width: 20px;
    height: 20px;
    border-radius: var(--radius-chip);
    background: var(--v-tint-mid);
    color: var(--v-fg);
    font-size: var(--fs-cap);
    line-height: 16px;
    font-weight: 600;
  }
  .kitchen {
    overflow: hidden;
    text-overflow: ellipsis;
    color: var(--v-fg);
    font-weight: 500;
  }
  .phonebar {
    position: sticky;
    top: var(--demo-h, 0px);
    z-index: 15;
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: calc(48px + env(safe-area-inset-top));
    padding: env(safe-area-inset-top) 8px 0;
    background: var(--v-app);
    border-bottom: 1px solid var(--v-line);
  }
  .pb-name {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    min-height: 44px;
    padding: 0 8px;
    border-radius: var(--radius-button);
    font-size: var(--fs-head);
    line-height: var(--lh-head);
    font-weight: 500;
    color: var(--v-fg);
    text-decoration: none;
  }
  .phonebar :global(.pb-go) {
    margin-right: 8px;
    color: var(--v-faint);
  }
  /* Thin, across the whole window, on demo kitchens only. */
  .demobar {
    position: sticky;
    top: 0;
    z-index: 30;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    height: var(--demo-h);
    padding: 0 16px;
    background: var(--v-shell);
    border-bottom: 1px solid var(--v-line);
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-muted);
  }
  .db-name {
    color: var(--v-muted);
  }
  .demobar :global([data-slot="button"]) {
    height: 24px;
    padding: 0 8px;
  }
  .rail .brand,
  .rail .lbl {
    display: none;
  }
  .rail .top {
    padding: 0;
    justify-content: center;
  }
  .rail .nav {
    width: 32px;
    padding: 0;
    justify-content: center;
  }
  .rail .nb {
    position: absolute;
    top: -4px;
    right: -10px;
  }

  .dock {
    position: fixed;
    left: 12px;
    right: 12px;
    bottom: calc(12px + env(safe-area-inset-bottom));
    z-index: 20;
    display: grid;
    grid-auto-flow: column;
    grid-auto-columns: 1fr;
    align-items: center;
    height: 64px;
    border-radius: var(--radius-card);
    background: var(--card);
    border: 1px solid var(--border);
  }
  .dock a {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 4px;
    height: 100%;
    font-size: 12px;
    line-height: 16px;
    font-weight: 500;
    color: var(--v-faint);
    text-decoration: none;
  }
  .dock a.on {
    color: var(--v-fg);
  }
  @media (max-width: 760px) {
    .v-main > .phonebar ~ .wrap {
      padding-top: 16px;
    }
  }
  .di {
    position: relative;
    display: inline-flex;
  }
  .db {
    position: absolute;
    top: -8px;
    left: 14px;
  }
  .db .nb {
    margin: 0;
  }
  .token {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: var(--v-dialog-pad);
  }
  .token h2 {
    margin: 0;
    font-size: var(--fs-body);
    line-height: var(--lh-body);
    font-weight: 600;
  }
  .token p {
    margin: 0;
    font-size: 13px;
    line-height: 20px;
    color: var(--v-muted);
  }
  .token p.bad {
    color: var(--v-bad-text);
  }
  /* One dialog button pattern: right-aligned, ghost Cancel, primary at its natural width. */
  .token-buttons {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 4px;
  }
</style>
