<script lang="ts">
  // One steady order: the lines that need the owner on top, each with one
  // sentence and one button; the rest as plain rows whose reasons fold.
  import { page } from "$app/state";
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import * as Collapsible from "@arlen/ui-kit/components/ui/collapsible";
  import { ApiError, api } from "$lib/api/client";
  import { owner } from "$lib/owner.svelte";
  import CodeField from "$lib/components/CodeField.svelte";
  import type { SteadyLine, SteadyOrder } from "$lib/api/types";
  import { bump, setChrome } from "$lib/chrome.svelte";
  import { LINE_RESULT, amount, look, money, nameWord, prose, sentences } from "$lib/format";
  import { live } from "$lib/live.svelte";
  import Drift from "$lib/components/Drift.svelte";
  import Frame from "$lib/components/Frame.svelte";

  const id = $derived(page.params.id ?? "");
  const steady = live(() => api.steadyOrder(id));
  const s = $derived(steady.data);

  $effect(() => setChrome(s?.name ?? "Steady order", { href: "/steady", label: "Steady orders" }));

  let busy = $state("");
  let problem = $state("");
  // A write the server refused for want of the approval code waits here
  // until the owner types it.
  let retry = $state<null | (() => void)>(null);

  async function act(key: string, fn: () => Promise<SteadyOrder>) {
    busy = key;
    problem = "";
    try {
      steady.data = await fn();
      bump();
      retry = null;
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) {
        const wrong = !!owner.code;
        owner.code = "";
        retry = () => act(key, fn);
        problem = wrong ? "That code is not right." : "";
      } else {
        problem = e instanceof Error ? e.message : String(e);
      }
    } finally {
      busy = "";
    }
  }

  const pending = $derived(!!s && s.lines.every((l) => l.result === "pending"));
  const asks = (l: SteadyLine) => l.result === "waiting" || l.result === "flagged";
  const acceptLabel = (l: SteadyLine) =>
    l.acceptLabel ?? (l.thisWeekQuantity !== undefined ? `Order ${l.thisWeekQuantity} now` : "Accept");
  const weekTotal = $derived(
    (s?.lines ?? []).filter((l) => !asks(l) && l.result !== "pending").reduce((t, l) => t + (l.totalCents ?? 0), 0),
  );
  // Amount and total in the label line, so the control slot holds one thing.
  const figures = (l: SteadyLine) =>
    l.thisWeekQuantity !== undefined
      ? `${amount(l.thisWeekQuantity, l.unit)}, ${money(l.totalCents)}`
      : `${amount(l.usualQuantity, l.unit)} usual`;
  const needsYou = $derived((s?.lines ?? []).filter(asks));
  const rest = $derived((s?.lines ?? []).filter((l) => !asks(l)));
  // The one sentence a waiting line shows: what the owner decides on.
  // "Waits for you because of the flag below" points at a folded flag, so the
  // flag's own first sentence stands in for it.
  const firstOf = (l: SteadyLine) => {
    const own = sentences(l.sentence)[0];
    const flag = sentences(l.flags[0]?.sentence)[0];
    return prose((own && !/flag below/i.test(own) ? own : flag ?? own) ?? "");
  };
  const waiting = $derived((s?.lines ?? []).filter(asks).length);
</script>

{#if s}
  <Frame title={s.name}>
    {#snippet head()}
      <p class="facts">
        <span>Every {s.weekday}</span>
        {#if pending}<span>not renewed this week</span>
        {:else}
          <span><b class="num">{money(weekTotal)}</b> ordered</span>
          {#if waiting}<span><b class="num">{waiting}</b> {waiting === 1 ? "needs" : "need"} you</span>{/if}
        {/if}
      </p>
    {/snippet}

    {#if pending}
      <div><Button id="renew" data-testid="renew" disabled={!!busy} onclick={() => act("renew", () => api.renew(s.id))}>Renew now</Button></div>
    {/if}

    {#if retry}
      <CodeField onready={retry} {problem} action="Continue" />
    {:else if problem}
      <p class="t-bad problem" role="alert">{problem}</p>
    {/if}

    {#if needsYou.length}
      <ul class="asks" aria-label="Lines that need you">
        {#each needsYou as l (l.productId)}
          <li class="ask" data-testid="line-{l.productId}" id="line-{l.productId}">
            <p class="ask-name">{nameWord(l.name)} <span class="t-quiet num">{figures(l)}</span></p>
            <p class="ask-why">{firstOf(l)}</p>
            <div>
              <Button
                variant="outline"
                id="accept-{l.productId}"
                data-testid="accept-{l.productId}"
                disabled={!!busy}
                onclick={() => act(l.productId, () => api.acceptLine(s!.id, l.productId))}
              >
                {acceptLabel(l)}
              </Button>
            </div>
            {@render fold(l, true)}
          </li>
        {/each}
      </ul>
    {/if}

    <ul class="rows" aria-label="Lines">
      {#each rest as l (l.productId)}
        {@const r = look(LINE_RESULT, l.result)}
        <li data-testid="line-{l.productId}" id="line-{l.productId}">
          <Collapsible.Root>
            <Collapsible.Trigger class="row">
              <span class="name">{nameWord(l.name)}</span>
              <span class="qty num">{figures(l)}</span>
              <span class="state">{l.result === "pending" ? "" : r.label}</span>
              <Collapsible.Chevron />
            </Collapsible.Trigger>
            {@render body(l, false)}
          </Collapsible.Root>
        </li>
      {/each}
    </ul>

    {#if s.simulatedHistory}
      <p class="foot t-quiet" id="simulated-history" data-testid="simulated-history">
        The {s.weeksLearned} weeks of history behind this order are simulated for the demo.
      </p>
    {/if}
  </Frame>
{:else if steady.error}
  <Frame title="Steady order">
    <p class="t-quiet">Cannot read {id}: {steady.error}</p>
  </Frame>
{/if}

{#snippet fold(l: SteadyLine, first: boolean)}
  <Collapsible.Root>
    <Collapsible.Trigger class="more-btn">
      <Collapsible.Chevron />
      Details
    </Collapsible.Trigger>
    {@render body(l, first)}
  </Collapsible.Root>
{/snippet}

{#snippet body(l: SteadyLine, first: boolean)}
  {@const shown = first ? firstOf(l) : ""}
  {@const said = sentences(l.sentence).filter((t) => !/^usual amount\.?$/i.test(t) && !/^median of/i.test(t) && prose(t) !== shown)}
  {@const flags = l.flags.filter((f) => !l.sentence.includes(f.sentence)).flatMap((f) => sentences(f.sentence)).filter((t) => prose(t) !== shown)}
  {@const chart = l.history && l.history.length > 1 && l.flags.some((f) => f.kind === "per_guest_up")}
  <Collapsible.Content forceMount>
    {#snippet child({ props, open })}
      <div {...props} hidden={!open} class="below">
        {#if said.length}<p class="why">{said.map(prose).join(" ")}</p>{/if}
        {#if flags.length}<p class="why">{flags.map(prose).join(" ")}</p>{/if}
        {#if l.split}
          <table class="split">
            <caption class="sr-only">How the line is split</caption>
            <tbody>
              {#each l.split.parts as p (p.productId)}
                <tr>
                  <td>{nameWord(p.name)} <span class="mono t-quiet">{p.productId}</span></td>
                  <td class="r num">{amount(p.quantity, p.unit)}</td>
                  <td class="r num">{money(p.totalCents)}</td>
                </tr>
              {/each}
              <tr class="sum-row">
                <td>Together, {money(l.split.extraCostCents)} ({l.split.extraCostPct}&nbsp;%) more</td>
                <td></td>
                <td class="r num">{money(l.split.totalCents)}</td>
              </tr>
            </tbody>
          </table>
        {/if}
        {#if chart && l.history}
          <Drift history={l.history} usual={l.usualQuantity} unit={l.unit} id="drift-{l.productId}" />
        {/if}
        <p class="pid"><span class="mono">{l.productId}</span>{#if l.orderId}<span>order <a href="/ledger">{l.orderId}</a></span>{/if}</p>
      </div>
    {/snippet}
  </Collapsible.Content>
{/snippet}

<style>
  .facts {
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem 1.25rem;
    margin: 0;
    font-size: var(--text-sm);
    color: var(--color-fg-secondary);
  }
  .facts b {
    font-weight: 500;
    color: var(--color-fg-primary);
  }
  .problem {
    margin: 0;
    font-size: var(--text-sm);
  }
  .asks,
  .rows {
    display: flex;
    flex-direction: column;
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .asks {
    gap: 1.5rem;
  }
  .ask {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .ask-name {
    margin: 0;
    font-size: var(--text-base);
    font-weight: 500;
  }
  .ask-why {
    margin: 0;
    max-width: 60ch;
    font-size: var(--text-sm);
    color: var(--color-fg-secondary);
  }
  .ask :global(.more-btn) {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    min-height: 2rem;
    font-size: var(--text-xs);
    color: var(--color-fg-secondary);
  }
  .rows li + li {
    border-top: 1px solid color-mix(in srgb, var(--foreground) 7%, transparent);
  }
  .rows :global(.row) {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto 9rem 1rem;
    gap: 1rem;
    align-items: baseline;
    width: 100%;
    padding: 0.55rem 0.35rem;
    border-radius: var(--radius-input);
    text-align: start;
  }
  .rows :global(.row:hover) {
    background: color-mix(in srgb, var(--color-fg-primary) 5%, transparent);
  }
  .name {
    font-size: var(--text-sm);
    font-weight: 500;
  }
  .qty {
    font-size: var(--text-sm);
    white-space: nowrap;
  }
  .state {
    font-size: var(--text-sm);
    color: var(--color-fg-secondary);
  }
  .rows :global(.kit-chevron) {
    align-self: center;
  }
  .below {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    padding: 0.25rem 0.35rem 0.75rem;
  }
  .why {
    margin: 0;
    max-width: 62ch;
    font-size: var(--text-sm);
    color: var(--color-fg-secondary);
  }
  .pid {
    display: flex;
    gap: 1rem;
    margin: 0;
    font-size: var(--text-2xs);
    color: var(--color-fg-secondary);
  }
  .pid a {
    color: inherit;
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  .split {
    width: 100%;
    max-width: 40rem;
    border-collapse: collapse;
    font-size: var(--text-xs);
  }
  .split td {
    padding: 0.35rem 0;
  }
  .split td + td {
    padding-inline-start: 1rem;
  }
  .split tr + tr td {
    border-top: 1px solid color-mix(in srgb, var(--foreground) 7%, transparent);
  }
  .sum-row td {
    font-weight: 500;
  }
  .r {
    text-align: end;
    white-space: nowrap;
  }
  .foot {
    margin: 0;
    font-size: var(--text-xs);
  }
  @media (max-width: 760px) {
    .rows :global(.row) {
      grid-template-columns: minmax(0, 1fr) 1rem;
      gap: 0.1rem 0.75rem;
    }
    .qty,
    .state {
      grid-column: 1;
      font-size: var(--text-xs);
    }
    .rows :global(.kit-chevron) {
      grid-column: 2;
      grid-row: 1;
    }
    .ask :global(button) {
      width: 100%;
    }
  }
</style>
