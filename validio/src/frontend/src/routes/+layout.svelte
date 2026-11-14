<script lang="ts">
  import "../app.css";
  import { onMount } from "svelte";
  import { afterNavigate, goto } from "$app/navigation";
  import { page } from "$app/state";
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import { Dialog } from "@arlen/ui-kit/components/ui/dialog";
  import { Input } from "@arlen/ui-kit/components/ui/input";
  import { notePage } from "@arlen/ui-kit/components/ui/page/history";
  import { CO_BRAND } from "$lib/brand";
  import { api, LIVE, needsToken } from "$lib/api/client";
  import { tokenPrompt } from "$lib/api/error";
  import { owner, session } from "$lib/owner.svelte";
  import { poll } from "$lib/poll";
  import { bump, chrome } from "$lib/chrome.svelte";
  import { Activity, Bot, ChevronDown, House, ShieldCheck } from "@lucide/svelte";

  let { children } = $props();

  // Four places, flat, as icon and word in the petrol band (the phone's tab bar at the bottom,
  // icon over word). The same icons as the v2 sidebar. The kitchen's name on the right opens Settings.
  const PAGES = [
    { href: "/", id: "nav-home", label: "Home", icon: House, match: (p: string) => p === "/" },
    { href: "/activity", id: "nav-activity", label: "Activity", icon: Activity, match: (p: string) => p.startsWith("/activity") },
    { href: "/rules", id: "nav-rules", label: "Rules", icon: ShieldCheck, match: (p: string) => p.startsWith("/rules") },
    { href: "/agent", id: "nav-agent", label: "Agent", icon: Bot, match: (p: string) => p.startsWith("/agent") },
  ];

  const path = $derived(page.url.pathname);
  // The login page stands alone: no band, no tab bar.
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
  // The grey strip above the band, on demo kitchens only.
  const demoBar = $derived(!!session.account?.isDemo);

  afterNavigate(({ to }) => {
    if (to?.url) notePage(to.url.pathname);
  });

  // What waits for the owner, on Home's nav word.
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
  <title>Validio</title><!-- one name in the tab on every page; the page says where you are -->
</svelte:head>

{#snippet waitCount(n: number)}
  <span class="nb num" aria-hidden="true">{n}</span><span class="sr-only">, {n} waiting</span>
{/snippet}

{#if door}
  <main class="v-main door-main">
    {@render children()}
  </main>
{:else if session.account}
  {#if demoBar}
    <!-- Presenter controls, apart from the product: a plain grey strip above everything. -->
    <div class="demobar" data-testid="demo-bar" id="demo-bar">
      <div class="col db-in">
        <span class="db-name">Demo kitchen</span>
        {#if session.account.demoCode}<span class="db-code">Approval code: <span class="num">{session.account.demoCode}</span></span>{/if}
        <button type="button" class="db-reset" id="demo-reset" data-testid="demo-reset" onclick={reset}>Start over</button>
      </div>
    </div>
  {/if}

  <header class="band" class:phone={chrome.phone}>
    <div class="col band-in">
      <a class="mark" href="/">
        <span class="wordmark">Validio</span>
        {#if CO_BRAND}<span class="for">{CO_BRAND}</span>{/if}
      </a>
      {#if !chrome.phone}
        <nav class="topnav" aria-label="Main">
          {#each PAGES as p (p.href)}
            <a href={p.href} id={p.id} data-testid={p.id} class:on={p.match(path)} aria-current={p.match(path) ? "page" : undefined}>
              <p.icon class="nav-icon" size={16} strokeWidth={1.75} aria-hidden="true" />{p.label}{#if p.href === "/" && waiting > 0}{@render waitCount(waiting)}{/if}
            </a>
          {/each}
        </nav>
        <a class="kitchen" href="/settings" id="nav-settings" data-testid="nav-settings" class:on={path.startsWith("/settings")} aria-current={path.startsWith("/settings") ? "page" : undefined}>
          <ChevronDown class="k-chev" size={14} strokeWidth={2} aria-hidden="true" />
          <span class="k-name">{session.account.name}</span>
          <span class="sr-only">, Settings</span>
        </a>
      {:else}
        <a class="kitchen" href="/settings" id="phone-settings" data-testid="phone-settings" aria-current={path.startsWith("/settings") ? "page" : undefined}>
          <ChevronDown class="k-chev" size={14} strokeWidth={2} aria-hidden="true" />
          <span class="k-name">{session.account.name}</span>
          <span class="sr-only">, Settings</span>
        </a>
      {/if}
    </div>
  </header>

  <main class="v-main">
    <div class="wrap">
      {@render children()}
    </div>
  </main>

  {#if chrome.phone}
    <nav class="dock" aria-label="Main">
      {#each PAGES as p (p.href)}
        <a href={p.href} id="{p.id}-tab" data-testid="{p.id}-tab" class:on={p.match(path)} aria-current={p.match(path) ? "page" : undefined}>
          <p.icon class="dock-icon" size={20} strokeWidth={1.75} aria-hidden="true" />
          <span>{p.label}{#if p.href === "/" && waiting > 0}{@render waitCount(waiting)}{/if}</span>
        </a>
      {/each}
    </nav>
  {/if}
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
      <h2 id="token-title">Start over failed</h2>
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
  .col {
    max-width: var(--v-col);
    margin: 0 auto;
    padding: 0 40px;
  }
  .v-main {
    min-width: 0;
  }
  .door-main {
    min-height: 100vh;
  }

  /* ---------- the demo strip ---------- */
  .demobar {
    background: var(--v-demo-bg);
    color: var(--v-demo-fg);
    font-size: var(--fs-cap);
    line-height: 16px;
  }
  .db-in {
    display: flex;
    align-items: center;
    gap: 24px;
    min-height: 30px;
  }
  .db-name {
    font-weight: 600;
    color: var(--v-demo-strong);
  }
  .db-code .num {
    margin-left: 2px;
  }
  .db-reset {
    margin-left: auto;
    padding: 4px 0;
    border: 0;
    background: none;
    font: inherit;
    color: inherit;
    cursor: pointer;
  }
  .db-reset:hover {
    color: var(--v-demo-strong);
    text-decoration: underline;
    text-underline-offset: 3px;
  }

  /* ---------- the petrol band ---------- */
  /* The band stays at the top while the page scrolls; the grey demo strip above it scrolls away. */
  .band {
    position: sticky;
    top: 0;
    z-index: 30;
    background: var(--valio-band);
    color: var(--valio-band-fg);
  }
  .kitchen :global(.k-chev) {
    flex: none;
    margin-right: -2px;
    opacity: 0.85;
  }
  .topnav :global(.nav-icon) {
    flex: none;
    opacity: 0.9;
  }
  .band-in {
    display: flex;
    align-items: stretch;
    gap: 40px;
    height: 60px;
  }
  .mark {
    display: flex;
    align-items: baseline;
    align-self: center;
    gap: 10px;
    flex: none;
    text-decoration: none;
    color: inherit;
  }
  .wordmark {
    font-family: var(--v-sans);
    font-size: 20px;
    line-height: 28px;
    font-weight: 700;
    letter-spacing: var(--ls-title);
  }
  .for {
    font-size: var(--fs-cap);
    line-height: 16px;
    color: var(--valio-band-muted);
  }
  .topnav {
    display: flex;
    align-items: stretch;
    gap: 28px;
    margin-left: 8px;
  }
  .topnav a,
  .kitchen {
    position: relative;
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: var(--fs-head);
    line-height: var(--lh-head);
    color: var(--valio-band-muted);
    text-decoration: none;
    white-space: nowrap;
    transition: color var(--duration-fast) ease;
  }
  .topnav a:hover,
  .kitchen:hover {
    color: var(--valio-band-fg);
  }
  .topnav a.on {
    color: var(--valio-band-fg);
    font-weight: 500;
  }
  .topnav a.on::after,
  .kitchen.on::after {
    content: "";
    position: absolute;
    left: 0;
    right: 0;
    bottom: 0;
    height: 2px;
    background: var(--valio-band-fg);
  }
  .nb {
    display: inline-grid;
    place-items: center;
    min-width: 18px;
    height: 18px;
    padding: 0 5px;
    border-radius: var(--radius-chip);
    background: var(--valio-band-fg);
    color: var(--valio-band);
    font-size: 11px;
    line-height: 18px;
    font-weight: 600;
  }
  .kitchen {
    margin-left: auto;
    justify-content: flex-end;
    min-width: 0;
    font-size: var(--fs-meta);
  }
  .k-name {
    max-width: 240px;
    overflow: hidden;
    text-overflow: ellipsis;
    color: var(--valio-band-fg);
    font-weight: 500;
  }
  @media (max-width: 1100px) {
    .for {
      display: none;
    }
    .band-in {
      gap: 28px;
    }
    .topnav {
      gap: 22px;
      margin-left: 0;
    }
    .k-name {
      max-width: 140px;
    }
  }

  /* ---------- the phone ---------- */
  .band.phone .band-in {
    height: 52px;
    gap: 16px;
  }
  .band.phone .col,
  .demobar .col {
    padding: 0 40px;
  }
  .band.phone .wordmark {
    font-size: 19px;
  }
  .band.phone .k-name {
    max-width: 180px;
    font-size: var(--fs-meta);
  }
  .band.phone .kitchen {
    min-height: 44px;
  }
  .dock {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 20;
    display: grid;
    grid-auto-flow: column;
    grid-auto-columns: 1fr;
    height: calc(56px + env(safe-area-inset-bottom));
    padding-bottom: env(safe-area-inset-bottom);
    background: var(--v-surface);
    border-top: 1px solid var(--v-line-strong);
  }
  .dock a {
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 2px;
    height: 56px;
    font-size: 12px;
    line-height: 16px;
    color: var(--v-muted);
    text-decoration: none;
  }
  .dock a span {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  .dock a.on {
    color: var(--valio);
    font-weight: 600;
  }
  .dock a.on::before {
    content: "";
    position: absolute;
    top: -1px;
    left: 18%;
    right: 18%;
    height: 3px;
    background: var(--valio);
  }
  .dock .nb {
    background: var(--valio);
    color: var(--v-on-valio);
  }
  @media (max-width: 760px) {
    .col,
    .band.phone .col,
    .demobar .col {
      padding: 0 16px;
    }
    .db-in {
      gap: 16px;
      min-height: 44px;
      font-size: 13px;
    }
    .db-reset {
      min-height: 44px;
      min-width: 44px;
    }
  }

  /* ---------- the token dialog ---------- */
  .token {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: var(--v-dialog-pad);
  }
  .token h2 {
    margin: 0;
    font-family: var(--v-sans);
    font-size: 19px;
    line-height: 26px;
    font-weight: 560;
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
  .token-buttons {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 4px;
  }
</style>
