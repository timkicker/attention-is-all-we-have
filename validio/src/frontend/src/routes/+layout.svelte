<script lang="ts">
  import "../app.css";
  import figtreeUrl from "@fontsource-variable/figtree/files/figtree-latin-wght-normal.woff2?url";
  import pacificoUrl from "@fontsource/pacifico/files/pacifico-latin-400-normal.woff2?url";
  import { onMount, tick } from "svelte";
  import { afterNavigate, goto, onNavigate } from "$app/navigation";
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
  import { Activity, Bot, House, ShieldCheck } from "@lucide/svelte";
  import { Tooltip } from "bits-ui";
  import { blurSwap, collapse, CSS_EASE, DUR, easeOut, fadeOut, reduced, viewTransition } from "$lib/motion";
  import { net, reportFail, reportOk, tick as clock } from "$lib/net.svelte";
  import { morph } from "$lib/peek.svelte";
  import { toast } from "$lib/toast.svelte";
  import { keyRouter, stepRows } from "$lib/keys";
  import { syncThemeColor } from "$lib/theme.svelte";
  import { AccountMenu, BusyLabel, Current, hm, money, Toaster } from "$lib/v2";
  import type PaletteT from "$lib/v2/Palette.svelte";

  let { children } = $props();

  // Four places, flat, as icon and word in the middle of the petrol band (the phone's tab bar at
  // the bottom, icon over word). The kitchen on the right is the account menu (plans/025, S1, S2).
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

  // Page transitions (plans/003): the content column crossfades with a small push in the
  // direction of travel; band, dock and demo strip stand still; a clicked row's title travels
  // into the next heading. A filter (same path) is not a page move.
  const depth = (p: string) => p.split("/").filter(Boolean).length;
  // The tabs in their order on screen: moving right, the new page comes in from the right.
  const TAB_ORDER = ["/", "/activity", "/rules", "/agent", "/settings"];
  const tabOf = (p: string) => {
    const top = "/" + (p.split("/").filter(Boolean)[0] ?? "");
    return TAB_ORDER.indexOf(top);
  };
  // A page change that takes longer than 300 ms runs the current along the band's foot (plans/025, F5).
  let slowNav = $state(false);
  let slowTimer: ReturnType<typeof setTimeout> | undefined;
  onNavigate(() => {
    clearTimeout(slowTimer);
    slowTimer = setTimeout(() => (slowNav = true), 300);
  });
  afterNavigate(() => {
    clearTimeout(slowTimer);
    slowNav = false;
  });

  onNavigate((nav) => {
    const doc = document as Document & { startViewTransition?: (cb: () => Promise<void>) => { finished: Promise<void> } };
    if (!doc.startViewTransition || reduced() || !nav.to || !nav.from) return;
    if (nav.from.url.pathname === nav.to.url.pathname) return;
    const a = depth(nav.from.url.pathname);
    const b = depth(nav.to.url.pathname);
    const ta = tabOf(nav.from.url.pathname);
    const tb = tabOf(nav.to.url.pathname);
    // Between tabs the content slides the way the tab bar moved; inside a tab, deeper or up.
    document.documentElement.dataset.navDir =
      ta !== tb && ta !== -1 && tb !== -1 ? (tb > ta ? "next" : "prev") : b > a ? "deeper" : b < a ? "up" : "across";
    // Home brings its own slow entrance: the page change under it is only a fade.
    if (nav.to.url.pathname === "/") document.documentElement.dataset.navTo = "home";
    return new Promise<void>((resolve) => {
      const t = doc.startViewTransition!(async () => {
        resolve();
        await nav.complete;
      });
      t.finished.finally(() => {
        morph.id = "";
        delete document.documentElement.dataset.navDir;
        delete document.documentElement.dataset.navTo;
      });
    });
  });

  afterNavigate(({ from, to, type }) => {
    if (to?.url) notePage(to.url.pathname);
    // Keyboard and screen reader users start at the new page's title (plans/018).
    if (type !== "enter" && from?.url.pathname !== to?.url.pathname)
      tick().then(() => document.querySelector<HTMLElement>("h1.v-title")?.focus({ preventScroll: true }));
  });

  // What waits for the owner, on Home's nav word; and the agent's news as notifications (plans/012).
  let waiting = $state(0);
  let seenWaiting: Set<string> | null = null;
  let seenLatest: Set<string> | null = null;
  let lastAgent = "";
  const count = async () => {
    if (!session.account) return;
    let h;
    try {
      h = await api.home();
      reportOk();
    } catch (e) {
      reportFail();
      throw e;
    }
    waiting = h.needsYou.length;
    const here = page.url.pathname;
    const at = (id: string) => here === `/activity/${encodeURIComponent(id)}` || here === `/activity/${id}`;
    if (seenWaiting && seenLatest) {
      for (const i of h.needsYou)
        if (!seenWaiting.has(i.id) && !at(i.id))
          toast({
            tone: "wait",
            title: "Waiting for you",
            body: i.totalCents != null ? `${i.title}, ${money(i.totalCents)}` : i.title,
            action: { href: `/activity/${encodeURIComponent(i.id)}?approve=1`, label: "Review" },
          });
      for (const i of h.latest)
        if (!seenLatest.has(i.id) && i.status === "blocked" && !at(i.id))
          toast({ tone: "bad", title: "Blocked", body: i.title, action: { href: `/activity/${encodeURIComponent(i.id)}`, label: "See why" } });
      if (h.agent.state === "consent" && lastAgent !== "consent" && here !== "/agent")
        toast({ tone: "wait", title: "Your agent called", body: "Check the code before you allow it", action: { href: "/agent", label: "Agent" } });
    }
    seenWaiting = new Set(h.needsYou.map((i) => i.id));
    seenLatest = new Set(h.latest.map((i) => i.id));
    lastAgent = h.agent.state;
  };
  onMount(() => poll(() => count().catch(() => {})));
  // A demo reset, an approval here, another account: what is on screen now is the new "seen".
  $effect(() => {
    void chrome.version;
    void session.account?.id;
    seenWaiting = seenLatest = null;
    if (session.account) count().catch(() => {});
  });
  onMount(syncThemeColor);

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
    resetting = true;
    try {
      // The kitchen is replaced: the whole page crossfades to the fresh one (plans/019).
      await viewTransition(async () => {
        await api.reset();
        bump();
        await goto("/");
      });
    } catch (e) {
      if (needsToken(e)) return; // the token dialog was closed
      demoProblem = e instanceof Error ? e.message : String(e);
      then = null;
      tokenOpen = true;
    } finally {
      resetting = false;
    }
  }
  let resetting = $state(false);

  // ⌘K and the few keys (plans/013). Nothing here animates. The palette loads on its first use, or
  // once the page is idle, so it is not in the first page's script (plans/025, F6).
  let palette = $state<PaletteT>();
  let PaletteC = $state<typeof PaletteT | null>(null);
  const loadPalette = async () => {
    if (!PaletteC) PaletteC = (await import("$lib/v2/Palette.svelte")).default;
  };
  async function openPalette(keys = false) {
    await loadPalette();
    await tick();
    palette?.open(keys);
  }
  onMount(() => {
    const idle = (globalThis as { requestIdleCallback?: (cb: () => void) => number }).requestIdleCallback;
    const t = setTimeout(() => (idle ? idle(() => void loadPalette()) : void loadPalette()), 2500);
    return () => clearTimeout(t);
  });
  function onKey(e: KeyboardEvent) {
    if (!session.account || door) return;
    if ((e.metaKey || e.ctrlKey) && !e.altKey && e.key.toLowerCase() === "k") {
      e.preventDefault();
      void openPalette();
      return;
    }
    const act = keyRouter(e, { path });
    if (!act) return;
    e.preventDefault();
    const filter = path === "/activity" && act && "go" in act && act.go.startsWith("/activity");
    if ("go" in act) void goto(act.go, { keepFocus: filter, noScroll: filter });
    else if ("rows" in act) stepRows(act.rows);
    else if ("find" in act) document.getElementById("activity-find")?.focus();
    else if ("approve" in act) void goto(act.approve);
    else void openPalette(act.palette === "keys");
  }
  // The badge: it appears from nine tenths with a fade, from its left edge (plans/019).
  const pop = (_n: Element) =>
    reduced() ? { duration: 120, css: (t: number) => `opacity:${t}` } : { duration: 200, easing: easeOut, css: (t: number) => `opacity:${t};transform:scale(${0.9 + 0.1 * t})` };

  // The page is no longer live (plans/025, F4): offline, or the polls failed for 4 s.
  onMount(() => clock(1000));
  const stale = $derived(!!session.account && !door && (!net.online || (net.failing && net.now - net.failingSince > 4000)));
  const staleText = $derived(
    (net.online ? "Reconnecting to Validio." : "You're offline.") + (net.lastOk ? ` Last updated ${hm(new Date(net.lastOk).toISOString())}.` : ""),
  );

  // The demo bar's code copies on a click (plans/025, S3).
  let codeCopied = $state(false);
  let codeTimer: ReturnType<typeof setTimeout> | undefined;
  async function copyCode(code: string) {
    try {
      await navigator.clipboard.writeText(code);
    } catch {
      return;
    }
    codeCopied = true;
    clearTimeout(codeTimer);
    codeTimer = setTimeout(() => (codeCopied = false), 1200);
  }

  // The chosen nav item: a spark runs along its underline now and then, and a faint sheen
  // passes over the word with it (plans/025, S1; the one glow the owner asked for).
  const sheen = (node: HTMLElement | undefined) => {
    if (!node || reduced()) return;
    node.animate(
      [
        { transform: "translateX(-100%)", opacity: 0 },
        { transform: "translateX(-20%)", opacity: 1, offset: 0.4 },
        { transform: "translateX(100%)", opacity: 0 },
      ],
      { duration: DUR.spark, easing: CSS_EASE.inOut },
    );
  };
  let sheenEl = $state<HTMLElement>();

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
  <link rel="preload" as="font" type="font/woff2" href={figtreeUrl} crossorigin="anonymous" />
  <link rel="preload" as="font" type="font/woff2" href={pacificoUrl} crossorigin="anonymous" />
  <!-- one name in the tab on every page, with what waits for the owner (plans/012) -->
  <title>{waiting > 0 && session.account ? `(${waiting}) Validio` : "Validio"}</title>
</svelte:head>

<svelte:window onkeydown={onKey} ononline={() => (net.online = true)} onoffline={() => (net.online = false)} />

{#snippet waitCount(n: number)}
  <span class="nb num" aria-hidden="true" in:pop out:fadeOut>{#key n}<span class="nb-n" in:blurSwap={{ y: 4 }}>{n}</span>{/key}</span><span class="sr-only">, {n} waiting</span>
{/snippet}

<Tooltip.Provider delayDuration={500} skipDelayDuration={300}>
{#if door}
  <main class="v-main door-main">
    {@render children()}
  </main>
{:else if session.account}
  {#if demoBar}
    <!-- Presenter controls, apart from the product: a plain grey strip above everything. -->
    <div class="demobar" data-testid="demo-bar" id="demo-bar" style:view-transition-name="v-demo">
      <div class="col db-in">
        <span class="db-name">Demo kitchen</span>
        {#if session.account.demoCode}
          {@const code = session.account.demoCode}
          <button type="button" class="db-code" data-testid="demo-code" onclick={() => copyCode(code)} aria-label="Approval code {code}, copy">
            Approval code:
            {#key codeCopied}<span class="num" in:blurSwap>{codeCopied ? "Copied" : code}</span>{/key}
          </button>
        {/if}
        <button type="button" class="db-reset" id="demo-reset" data-testid="demo-reset" onclick={reset} disabled={resetting}><BusyLabel busy={resetting} idle="Start over" working="Starting over" /></button>
      </div>
    </div>
  {/if}

  <header class="band" class:phone={chrome.phone} style:view-transition-name="v-band">
    <div class="col band-in">
      <a class="mark" href="/" aria-label="Validio, Home">
        <span class="wordmark">Validio</span>
        {#if CO_BRAND}<span class="for">{CO_BRAND}</span>{/if}
      </a>
      {#if !chrome.phone}
        <nav class="topnav" aria-label="Main">
          {#each PAGES as p (p.href)}
            {@const on = p.match(path)}
            <a href={p.href} id={p.id} data-testid={p.id} class:on aria-current={on ? "page" : undefined}>
              <p.icon class="nav-icon" size={16} strokeWidth={1.75} aria-hidden="true" />
              <span class="nav-word">{p.label}</span>
              {#if p.href === "/" && waiting > 0}{@render waitCount(waiting)}{/if}
              {#if on}
                <span class="nav-sheen" aria-hidden="true"><span bind:this={sheenEl}></span></span>
                <span class="nav-ink" style:view-transition-name="v-nav-ink">
                  <Current tone="band" mode="listen" base="lit" pause={2400} onspark={() => sheen(sheenEl)} />
                </span>
              {/if}
            </a>
          {/each}
        </nav>
      {/if}
      <div class="band-end">
        <AccountMenu account={session.account} phone={chrome.phone} current={path.startsWith("/settings")} onkeys={() => openPalette(true)} />
      </div>
    </div>
    {#if slowNav}
      <span class="nav-prog" aria-hidden="true" out:fadeOut><Current tone="band" mode="listen" base="none" pause={0} /></span>
    {/if}
    {#if stale}
      <div class="stale" role="status" data-testid="net-stale" transition:collapse={{ duration: 200 }}>
        <div class="col stale-in">{staleText}</div>
      </div>
    {/if}
  </header>

  <main class="v-main">
    <div class="wrap">
      {@render children()}
    </div>
  </main>

  {#if chrome.phone}
    <nav class="dock" aria-label="Main" style:view-transition-name="v-dock">
      {#each PAGES as p (p.href)}
        <a href={p.href} id="{p.id}-tab" data-testid="{p.id}-tab" class:on={p.match(path)} aria-current={p.match(path) ? "page" : undefined}>
          {#if p.match(path)}<span class="dock-ink" style:view-transition-name="v-dock-ink" aria-hidden="true"><Current mode="listen" base="lit" pause={3200} thickness={3} /></span>{/if}
          <span class="nav-ic">
            <p.icon class="dock-icon" size={20} strokeWidth={1.75} aria-hidden="true" />
            {#if p.href === "/" && waiting > 0}{@render waitCount(waiting)}{/if}
          </span>
          <span>{p.label}</span>
        </a>
      {/each}
    </nav>
  {/if}
  <Toaster />
  {#if PaletteC}<PaletteC bind:this={palette} onreset={session.account.isDemo ? reset : undefined} />{/if}
{/if}

</Tooltip.Provider>

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
    {#if demoProblem}<p class="bad" id="token-problem" data-testid="token-problem" in:collapse={{ duration: 200 }}>{demoProblem}</p>{/if}
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
  .db-code {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 0;
    border: 0;
    background: none;
    font: inherit;
    color: inherit;
    border-radius: var(--radius-chip);
  }
  .db-code .num {
    display: inline-block;
    min-width: 6ch;
    color: var(--v-demo-strong);
    font-weight: 500;
    text-decoration: underline;
    text-decoration-color: transparent;
    text-underline-offset: 3px;
    transition: text-decoration-color var(--duration-fast) ease;
  }
  @media (hover: hover) and (pointer: fine) {
    .db-code:hover .num {
      text-decoration-color: currentColor;
    }
  }
  .db-reset {
    margin-left: auto;
    padding: 4px 0;
    border: 0;
    background: none;
    font: inherit;
    color: inherit;
    cursor: pointer;
    text-decoration: underline;
    text-decoration-color: transparent;
    text-underline-offset: 3px;
    transition:
      color var(--duration-fast) ease,
      text-decoration-color var(--duration-fast) ease,
      transform var(--v-dur-press) var(--v-ease-out);
  }
  @media (hover: hover) and (pointer: fine) {
    .db-reset:hover {
      color: var(--v-demo-strong);
      text-decoration-color: currentColor;
    }
  }
  .db-reset:active {
    transform: scale(0.97);
  }

  /* ---------- the petrol band ---------- */
  /* The band stays at the top while the page scrolls; the grey demo strip above it scrolls away.
     Three columns: the wordmark, the nav exactly in the middle of the screen, the account. */
  .band {
    position: sticky;
    top: 0;
    z-index: 30;
    background: var(--valio-band);
    color: var(--valio-band-fg);
  }
  .band-in {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
    align-items: stretch;
    column-gap: 32px;
    height: 60px;
  }
  .mark {
    display: flex;
    align-items: baseline;
    align-self: center;
    justify-self: start;
    gap: 10px;
    min-width: 0;
    text-decoration: none;
    color: inherit;
    border-radius: var(--radius-button);
  }
  .mark:focus-visible {
    outline-color: var(--valio-band-fg);
  }
  /* The wordmark in a heavy brush script, white on the petrol band. */
  .wordmark {
    font-family: var(--v-script);
    font-size: 26px;
    line-height: 34px;
    font-weight: 400;
    letter-spacing: 0;
  }
  .for {
    font-size: var(--fs-cap);
    line-height: 16px;
    color: var(--valio-band-muted);
    white-space: nowrap;
  }
  .topnav {
    display: flex;
    align-items: stretch;
    justify-content: center;
    gap: 6px;
  }
  .topnav a {
    position: relative;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 0 14px;
    font-size: var(--fs-head);
    line-height: var(--lh-head);
    color: var(--valio-band-muted);
    text-decoration: none;
    white-space: nowrap;
    transition: color var(--duration-fast) ease;
  }
  @media (hover: hover) and (pointer: fine) {
    .topnav a:hover {
      color: var(--valio-band-fg);
    }
    .topnav a:hover :global(.nav-icon) {
      transform: translateY(-1px);
    }
  }
  .topnav a:active .nav-word {
    transform: scale(0.97);
  }
  .nav-word {
    transition: transform var(--v-dur-press) var(--v-ease-out);
  }
  .topnav a:focus-visible {
    outline-color: var(--valio-band-fg);
    outline-offset: -2px;
    color: var(--valio-band-fg);
  }
  .topnav a.on {
    color: var(--valio-band-fg);
    font-weight: 500;
  }
  .topnav :global(.nav-icon) {
    flex: none;
    opacity: 0.9;
    transition: transform var(--v-dur-ui) var(--v-ease-out);
  }
  /* The icon carries the waiting count on its corner, so the words never move when it comes or goes. */
  .nav-ic {
    position: relative;
    display: inline-grid;
    place-items: center;
  }
  /* The waiting count sits in the item's top right corner, in its padding, so no word ever moves. */
  .topnav a > :global(.nb) {
    position: absolute;
    top: 9px;
    right: -6px;
  }
  /* The selected mark is an element of its own, so it can travel between words (plans/015);
     inside it the current runs (plans/025). */
  .nav-ink {
    position: absolute;
    left: 14px;
    right: 14px;
    bottom: 0;
    height: 2px;
  }
  .nav-sheen {
    position: absolute;
    inset: 0;
    overflow: hidden;
    pointer-events: none;
  }
  .nav-sheen > span {
    position: absolute;
    top: 0;
    bottom: 0;
    left: 0;
    width: 100%;
    background: var(--v-current-band-sheen);
    opacity: 0;
  }
  .nb {
    display: inline-grid;
    place-items: center;
    min-width: 16px;
    height: 16px;
    padding: 0 4px;
    border-radius: var(--radius-chip);
    background: var(--valio-band-fg);
    color: var(--valio-band);
    font-size: 10px;
    line-height: 16px;
    font-weight: 700;
  }
  .nb-n {
    display: inline-block;
  }
  .band-end {
    display: flex;
    align-items: stretch;
    justify-content: flex-end;
    justify-self: end;
    min-width: 0;
  }
  /* A slow page change: the current runs along the band's foot. */
  .nav-prog {
    position: absolute;
    left: 0;
    right: 0;
    bottom: 0;
    height: 2px;
  }
  /* The page is not live: one quiet line under the band. */
  .stale {
    background: var(--v-demo-bg);
    color: var(--v-demo-fg);
    border-bottom: 1px solid var(--v-line);
    font-size: var(--fs-cap);
    line-height: 16px;
  }
  .stale-in {
    padding-block: 7px;
  }
  @media (max-width: 1100px) {
    .for {
      display: none;
    }
    .band-in {
      column-gap: 16px;
    }
    .topnav a {
      padding: 0 10px;
    }
    .nav-ink {
      left: 10px;
      right: 10px;
    }
  }

  /* ---------- the phone ---------- */
  .band.phone .band-in {
    grid-template-columns: auto minmax(0, 1fr);
    height: 52px;
    column-gap: 16px;
  }
  .band.phone .col,
  .demobar .col {
    padding: 0 40px;
  }
  .band.phone .wordmark {
    font-size: 22px;
    line-height: 30px;
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
  .dock :global(.dock-icon) {
    transition: transform var(--v-dur-press) var(--v-ease-out);
  }
  .dock a:active :global(.dock-icon) {
    transform: scale(0.95);
  }
  .dock a:focus-visible {
    outline-offset: -2px;
  }
  .dock-ink {
    position: absolute;
    top: -1px;
    left: 18%;
    right: 18%;
    height: 3px;
  }
  .dock .nb {
    background: var(--valio);
    color: var(--v-on-valio);
  }
  .dock .nav-ic :global(.nb) {
    top: -6px;
    left: 13px;
    box-shadow: 0 0 0 2px var(--v-surface);
  }
  @media (max-width: 760px) {
    .col,
    .band.phone .col,
    .demobar .col {
      padding: 0 16px;
    }
    .db-in {
      gap: 16px;
      min-height: 36px;
      font-size: 13px;
    }
    .db-reset,
    .db-code {
      min-height: 44px;
      min-width: 44px;
      margin-block: -4px;
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
