<script lang="ts">
  import "../app.css";
  import { onMount } from "svelte";
  import { afterNavigate, goto } from "$app/navigation";
  import { page } from "$app/state";
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import { Badge } from "@arlen/ui-kit/components/ui/badge";
  import { Dialog } from "@arlen/ui-kit/components/ui/dialog";
  import { Input } from "@arlen/ui-kit/components/ui/input";
  import * as Tooltip from "@arlen/ui-kit/components/ui/tooltip";
  import { notePage } from "@arlen/ui-kit/components/ui/page/history";
  import { CalendarSync, ChevronRight, Inbox, PanelLeft, ScrollText, ShieldCheck } from "@lucide/svelte";
  import { api, LIVE, needsToken } from "$lib/api/client";
  import { tokenPrompt } from "$lib/api/error";
  import type { AskOut } from "$lib/api/types";
  import { askSummary } from "$lib/ask";
  import { owner } from "$lib/owner.svelte";
  import { CLOCK, dayTime, nb } from "$lib/format";
  import { poll } from "$lib/poll";
  import { bump, chrome, demoActions } from "$lib/chrome.svelte";

  let { children } = $props();

  const AREAS = [
    {
      label: "Orders",
      icon: Inbox,
      pages: [
        { href: "/", id: "nav-inbox", label: "Inbox", short: "Inbox", icon: Inbox, match: (p: string) => p === "/" || p.startsWith("/requests") || p.startsWith("/approve") },
        { href: "/steady", id: "nav-steady-orders", label: "Steady orders", short: "Steady", icon: CalendarSync, match: (p: string) => p.startsWith("/steady") },
      ],
    },
    {
      label: "Trust",
      icon: ShieldCheck,
      pages: [
        { href: "/spend-pass", id: "nav-spend-pass", label: "Spend Pass", short: "Pass", icon: ShieldCheck, match: (p: string) => p.startsWith("/spend-pass") },
        { href: "/ledger", id: "nav-open-ledger", label: "Ledger", short: "Ledger", icon: ScrollText, match: (p: string) => p.startsWith("/ledger") },
      ],
    },
  ];
  const PAGES = AREAS.flatMap((a) => a.pages);

  const path = $derived(page.url.pathname);
  // The approve page has its own bottom bar: no dock under it.
  const approve = $derived(path.startsWith("/approve"));

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

  let waiting = $state(0);
  const count = async () => {
    const items = await api.inbox();
    waiting = items.filter((i) => i.status === "waiting").length;
  };
  onMount(() => poll(count));
  $effect(() => {
    void chrome.version;
    count().catch(() => {});
    api.demoState().then((d) => (chrome.stockIsOut = d.stockOut466375), () => {});
  });

  // Any write the server refused for want of the token (a demo switch, or
  // every write on the public link) opens the token dialog; the client sends
  // the write again once the presenter typed it (api/client.ts, gated).
  let tokenOpen = $state(false);
  let tokenValue = $state("");
  let then = $state<null | (() => void)>(null);
  let demoProblem = $state("");
  let answerToken: null | ((ok: boolean) => void) = null;
  tokenPrompt.ask = () =>
    new Promise<boolean>((resolve) => {
      answerToken?.(false);
      answerToken = resolve;
      tokenValue = "";
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

  async function demo(fn: () => Promise<unknown>, next: string) {
    demoProblem = "";
    try {
      await fn();
      bump();
      await goto(next);
    } catch (e) {
      if (needsToken(e)) return; // the presenter closed the token dialog
      demoProblem = e instanceof Error ? e.message : String(e);
      then = null;
      tokenOpen = true;
    }
  }
  // The fixture answers at once; with the backend the kitchen's agent asks again first.
  demoActions.stockOut = () => demo(() => api.stockOut(true), "/");
  demoActions.stockBack = () => demo(() => api.stockOut(false), page.url.pathname);
  demoActions.ask = async () => {
    askOpen = true;
  };

  // "Ask as the kitchen's agent": the owner's own text goes through the same
  // agent loop as `make agent`; the dialog shows its calls, then the request.
  // One recorded example for each ending: ordered alone, waits for you, blocked.
  const EXAMPLES = ["100 litres of whipping cream by Monday", "50 kg of quark by Monday, budget 100 euro", "20 kg of parmesan by Monday"];
  let askOpen = $state(false);
  let askText = $state("");
  let asking = $state(false);
  let askProblem = $state("");
  let answer = $state<AskOut | null>(null);
  let summary = $state<string[]>([]);
  async function sendAsk(e?: SubmitEvent) {
    e?.preventDefault();
    const text = askText.trim();
    if (!text || asking) return;
    asking = true;
    askProblem = "";
    answer = null;
    summary = [];
    try {
      const a = await api.ask(text);
      // The lines come from the request itself; without one, the agent's last sentence.
      // Without a request, the first sentence of the agent's last words; the rest stays in the log.
      const first = a.final.split(/(?<=\.)\s/)[0];
      summary = a.requestId ? await api.request(a.requestId).then(askSummary, () => [first]) : [first];
      answer = a;
      bump();
    } catch (err) {
      if (!needsToken(err)) askProblem = err instanceof Error ? err.message : String(err);
    } finally {
      asking = false;
    }
  }
  function closeAsk() {
    askOpen = false;
    answer = null;
    summary = [];
    askProblem = "";
  }
  demoActions.reset = () => demo(() => api.reset(), "/");

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
  <span class="nb"><Badge variant="outline" class="v-count" aria-hidden="true">{n}</Badge></span>
  <span class="sr-only">, {n} waiting</span>
{/snippet}

<div class="shell" class:rail class:phone={chrome.phone}>
  {#if !chrome.phone}
    <aside class="side">
      <div class="top">
        <span class="brand">Validio</span>
        {#if !mid}
          <Button variant="ghost" size="icon-sm" class="fold" aria-label={folded ? "Open the sidebar" : "Fold the sidebar"} aria-pressed={folded} onclick={() => (folded = !folded)}>
            <PanelLeft />
          </Button>
        {/if}
      </div>
      <nav aria-label="Main">
        {#each AREAS as area (area.label)}
          <div class="nav area"><area.icon size={16} strokeWidth={1.75} aria-hidden="true" /><span class="lbl">{area.label}</span></div>
          <div class="sub">
            {#each area.pages as p (p.href)}
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
                  <span class="lbl">{p.label}</span>
                  {#if p.href === "/" && waiting > 0}{@render navBadge(waiting)}{/if}
                </a>
              {/if}
            {/each}
          </div>
        {/each}
      </nav>
      <div class="foot">
        <span class="kitchen">Hotel Espoo kitchen</span>
        <span class="clock num">{dayTime(CLOCK)}</span>
      </div>
    </aside>
  {/if}

  <main class="v-main">
    <div class="wrap" class:narrow={approve}>
      {@render children()}
    </div>
  </main>
</div>

{#if chrome.phone && !approve}
  <nav class="dock" aria-label="Main">
    {#each PAGES as p (p.href)}
      <a href={p.href} id={p.id} data-testid={p.id} class:on={p.match(path)} aria-current={p.match(path) ? "page" : undefined}>
        <span class="di"><p.icon size={20} strokeWidth={1.75} aria-hidden="true" />{#if p.href === "/" && waiting > 0}<span class="db">{@render navBadge(waiting)}</span>{/if}</span>
        <span>{p.short}</span>
      </a>
    {/each}
  </nav>
{/if}

<Dialog open={tokenOpen} onClose={closeToken} labelledby="token-title" size="sm">
  <form class="token" onsubmit={useToken}>
    <h2 id="token-title">{then || !demoProblem ? "Demo token" : "Demo control failed"}</h2>
    {#if then || !demoProblem}
      <label for="demo-token-input">The presenter's token. Kept until you close the page.</label>
      <Input id="demo-token-input" bind:value={tokenValue} autocomplete="off" aria-invalid={demoProblem ? true : undefined} />
    {/if}
    {#if demoProblem}<p class="bad">{demoProblem}</p>{/if}
    <div class="token-buttons">
      <Button variant="outline" onclick={closeToken}>Cancel</Button>
      {#if then || !demoProblem}<Button type="submit">{then ? "Use and run" : "Use"}</Button>{/if}
    </div>
  </form>
</Dialog>

<Dialog open={askOpen} onClose={closeAsk} labelledby="ask-title" size="md">
  <form class="token ask" onsubmit={sendAsk} data-testid="ask-dialog">
    <h2 id="ask-title">Ask as the kitchen's agent</h2>
    <label for="ask-input">What the kitchen needs. The agent sends it to Validio with the Spend Pass.</label>
    <Input id="ask-input" data-testid="ask-input" bind:value={askText} maxlength={300} autocomplete="off" placeholder={EXAMPLES[0]} />
    <p class="ex">
      Recorded at Valio:
      {#each EXAMPLES as x, i (x)}<button type="button" class="ex-btn" onclick={() => (askText = x)}>{x}</button>{i < EXAMPLES.length - 1 ? ", " : "."}{/each}
    </p>
    {#if asking}<p role="status">The agent is asking Validio…</p>{/if}
    {#if answer}
      <ul class="summary" data-testid="ask-summary" role="status">
        {#each summary as l, i (i)}<li>{nb(l)}</li>{/each}
      </ul>
      {#if answer.lines.length}
        <details class="fold ask-log" data-testid="ask-log">
          <summary><ChevronRight class="chev" aria-hidden="true" />Agent log</summary>
          <ol class="lines">
            {#each answer.lines as l, i (i)}<li>{l}</li>{/each}
          </ol>
        </details>
      {/if}
      {#if answer.requestId}
        <a class="open" href="/requests/{answer.requestId}" data-testid="ask-open" onclick={closeAsk}>Open {answer.requestId} ›</a>
      {/if}
    {/if}
    {#if askProblem}<p class="bad" role="alert">{askProblem}</p>{/if}
    <div class="token-buttons">
      <Button variant="outline" onclick={closeAsk}>Close</Button>
      <Button type="submit" data-testid="ask-send" disabled={asking || !askText.trim()}>Send</Button>
    </div>
  </form>
</Dialog>

{#if LIVE}<span hidden id="live-mode"></span>{/if}

<style>
  .shell {
    position: relative;
    display: grid;
    grid-template-columns: 208px minmax(0, 1fr);
    min-height: 100vh;
  }
  /* The sidebar's colour runs the whole page height, also past the sticky panel. */
  .shell:not(.phone)::before {
    content: "";
    position: absolute;
    inset: 0 auto 0 0;
    width: 208px;
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
    top: 0;
    height: 100vh;
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
  .sub {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .sub + .nav.area {
    margin-top: 12px;
  }
  .nav {
    position: relative;
    display: flex;
    align-items: center;
    gap: 12px;
    height: 32px;
    padding: 0 8px;
    border-radius: 6px;
    font-size: 13px;
    line-height: 20px;
    color: var(--v-muted);
    white-space: nowrap;
    text-decoration: none;
  }
  .nav.area {
    font-weight: 500;
    color: var(--v-fg);
  }
  .nav.area :global(svg) {
    color: var(--v-faint);
  }
  .sub .nav {
    padding-left: 36px;
  }
  a.nav:hover:not(.on) {
    background: color-mix(in srgb, var(--v-fg) 6%, transparent);
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
    display: flex;
    flex-direction: column;
    padding: 8px;
    white-space: nowrap;
    overflow: hidden;
  }
  .kitchen {
    font-size: 13px;
    line-height: 20px;
    font-weight: 500;
  }
  .clock {
    font-size: 12px;
    line-height: 16px;
    color: var(--v-faint);
  }
  .rail .brand,
  .rail .nav.area,
  .rail .foot {
    display: none;
  }
  .rail .top {
    padding: 0;
    justify-content: center;
  }
  .rail .sub .nav {
    width: 32px;
    padding: 0;
    justify-content: center;
  }
  .rail .sub + .nav.area + .sub {
    margin-top: 12px;
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
    border-radius: 12px;
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
    padding: 24px;
  }
  .token h2 {
    margin: 0;
    font-size: 15px;
    line-height: 22px;
    font-weight: 600;
  }
  .token label,
  .token p {
    margin: 0;
    font-size: 13px;
    line-height: 20px;
    color: var(--v-muted);
  }
  .token p.bad {
    color: var(--v-bad-text);
  }
  .ask .ex {
    font-size: 13px;
  }
  .ex-btn {
    padding: 0;
    border: 0;
    background: none;
    color: var(--v-fg);
    font: inherit;
    text-decoration: underline;
    text-underline-offset: 2px;
    cursor: pointer;
  }
  .lines {
    margin: 0;
    padding: 8px 0 0;
    list-style: none;
    white-space: pre-wrap;
    font-size: 13px;
    line-height: 20px;
    color: var(--v-muted);
    max-height: 240px;
    overflow: auto;
    overflow-wrap: anywhere;
  }
  .lines li + li {
    margin-top: 6px;
  }
  .summary {
    margin: 0;
    padding: 12px 0 0;
    list-style: none;
    border-top: 1px solid var(--v-line);
    font-size: 13px;
    line-height: 20px;
    color: var(--v-fg);
  }
  .summary li + li {
    margin-top: 4px;
  }
  .ask .open {
    font-size: 13px;
    color: var(--v-fg);
  }
  .token-buttons {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    margin-top: 8px;
  }
</style>
