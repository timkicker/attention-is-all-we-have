<script lang="ts">
  // One steady order in one kit Section: the lines that need the owner first,
  // each with one conclusion and one button; then the plain lines with their
  // state. Reasons, figures and the drift chart fold under each line.
  import { page } from "$app/state";
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import * as Collapsible from "@arlen/ui-kit/components/ui/collapsible";
  import { Row } from "@arlen/ui-kit/components/ui/row";
  import { Section } from "@arlen/ui-kit/components/ui/section";
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
  // One conclusion per line that waits, and what its button does.
  const conclusion = (l: SteadyLine) => {
    const up = l.flags.find((f) => f.kind === "per_guest_up");
    if (up && up.pct !== undefined) {
      const does = l.thisWeekQuantity !== undefined ? ` ${acceptLabel(l)} orders the usual ${amount(l.thisWeekQuantity, l.unit)}.` : "";
      return `Use per guest went up ${up.pct} % in two weeks.${does}`;
    }
    const broke = /would break a rule: ([^:;.]+)/.exec(l.sentence)?.[1];
    const own = firstOf(l).replace(/\.$/, "");
    return broke ? `${own}; the only substitute is ${broke.toLowerCase()}.` : firstOf(l);
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

    <Section>
      {#each needsYou as l (l.productId)}
        <div class="line" data-testid="line-{l.productId}" id="line-{l.productId}">
          <Row label={nameWord(l.name)} description={conclusion(l)}>
            {#snippet control()}
              <Button
                variant="outline"
                id="accept-{l.productId}"
                data-testid="accept-{l.productId}"
                disabled={!!busy}
                onclick={() => act(l.productId, () => api.acceptLine(s!.id, l.productId))}
              >
                {acceptLabel(l)}
              </Button>
            {/snippet}
            {#snippet below()}{@render fold(l)}{/snippet}
          </Row>
        </div>
      {/each}
      {#each rest as l (l.productId)}
        {@const r = look(LINE_RESULT, l.result)}
        <div class="line" data-testid="line-{l.productId}" id="line-{l.productId}">
          <Row label={nameWord(l.name)} description={figures(l)}>
            {#snippet control()}<span class="state">{l.result === "pending" ? "" : r.label}</span>{/snippet}
            {#snippet below()}{@render fold(l)}{/snippet}
          </Row>
        </div>
      {/each}
    </Section>

    {#if s.simulatedHistory}
      <!-- The demo notice itself lives in the ⋯ menu. -->
      <p hidden id="simulated-history" data-testid="simulated-history">
        Simulated history: the {s.weeksLearned} weeks behind this order are simulated for the demo.
      </p>
    {/if}
  </Frame>
{:else if steady.error}
  <Frame title="Steady order">
    <p class="t-quiet">Cannot read {id}: {steady.error}</p>
  </Frame>
{/if}

{#snippet fold(l: SteadyLine)}
  <Collapsible.Root>
    <Collapsible.Trigger class="more-btn">
      <Collapsible.Chevron />
      Details
    </Collapsible.Trigger>
    {@render body(l)}
  </Collapsible.Root>
{/snippet}

{#snippet body(l: SteadyLine)}
  {@const shown = asks(l) ? conclusion(l) : ""}
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
        {#if asks(l)}<p class="why num">{figures(l)}</p>{/if}
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
  .line :global(.more-btn) {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    min-height: 1.75rem;
    font-size: var(--text-xs);
    color: var(--color-fg-secondary);
  }
  .state {
    font-size: var(--text-sm);
    color: var(--color-fg-secondary);
    white-space: nowrap;
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
  @media (max-width: 760px) {
    .line :global(.row-main) {
      flex-wrap: wrap;
    }
  }
</style>
