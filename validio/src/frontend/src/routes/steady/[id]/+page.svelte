<script lang="ts">
  // One steady order as settings rows: each line says what this week brings
  // and why, its state and total sit in the control column, and a line that
  // waits carries its one button there too.
  import { page } from "$app/state";
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import { Notice } from "@arlen/ui-kit/components/ui/notice";
  import { Page } from "@arlen/ui-kit/components/ui/page";
  import { Row } from "@arlen/ui-kit/components/ui/row";
  import { Section } from "@arlen/ui-kit/components/ui/section";
  import { SectionGrid } from "@arlen/ui-kit/components/ui/section-grid";
  import { ApiError, api } from "$lib/api/client";
  import { owner } from "$lib/owner.svelte";
  import CodeField from "$lib/components/CodeField.svelte";
  import type { SteadyLine, SteadyOrder } from "$lib/api/types";
  import { bump, chrome, setChrome } from "$lib/chrome.svelte";
  import { LINE_RESULT, amount, dayTime, look, money, nameWord, prose } from "$lib/format";
  import { live } from "$lib/live.svelte";
  import Drift from "$lib/components/Drift.svelte";
  import Facts from "$lib/components/Facts.svelte";
  import State from "$lib/components/State.svelte";

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
  const waiting = $derived((s?.lines ?? []).filter(asks).length);
</script>

{#if s}
  <Page title={s.name} back={chrome.phone ? undefined : { href: "/steady", label: "Steady orders" }}>
    <SectionGrid>
    <div class="top">
      <Facts
        items={[
          { value: s.weekday, label: "every", before: true },
          { value: String(s.guestsPerWeek), label: "guests a week" },
          { value: String(s.weeksLearned), label: "weeks learned" },
          ...(pending ? [{ value: "not renewed", label: "this week", before: true }] : [{ value: money(weekTotal), label: "ordered this week" }, { value: String(waiting), label: "need a look" }]),
        ]}
      />
      {#if pending}
        <Button id="renew" data-testid="renew" disabled={!!busy} onclick={() => act("renew", () => api.renew(s.id))}>Renew now</Button>
      {:else if s.renewedAt}
        <span class="t-quiet renewed">Renewed {dayTime(s.renewedAt)}</span>
      {/if}
    </div>

    {#if s.simulatedHistory}
      <div id="simulated-history" data-testid="simulated-history">
        <Notice tone="neutral" text="Simulated history. The {s.weeksLearned} weeks behind this order are made up for the demo; the stock and prices are Valio's." />
      </div>
    {/if}

    {#if retry}
      <div class="ask"><CodeField onready={retry} {problem} action="Continue" /></div>
    {:else if problem}
      <p class="t-bad problem" role="alert">{problem}</p>
    {/if}

    <Section>
      {#each s.lines as l (l.productId)}
        {@const r = look(LINE_RESULT, l.result)}
        <div data-testid="line-{l.productId}">
        <Row label={nameWord(l.name)} description={l.sentence && !/^usual amount\.?$/i.test(l.sentence) ? prose(l.sentence) : undefined} id="line-{l.productId}">
          {#snippet control()}
            <span class="ctl">
              <span class="qty num">
                {#if l.thisWeekQuantity !== undefined}{amount(l.thisWeekQuantity, l.unit)}{:else}{amount(l.usualQuantity, l.unit)} usual{/if}
              </span>
              <span class="sum num">{money(l.totalCents)}</span>
              {#if l.result !== "pending"}<State label={r.label} tone={r.tone} />{/if}
              {#if asks(l)}
                <Button
                  variant="outline"
                  size="sm"
                  id="accept-{l.productId}"
                  data-testid="accept-{l.productId}"
                  disabled={!!busy}
                  onclick={() => act(l.productId, () => api.acceptLine(s!.id, l.productId))}
                >
                  {acceptLabel(l)}
                </Button>
              {/if}
            </span>
          {/snippet}
          {#snippet below()}
            {@render more(l)}
          {/snippet}
        </Row>
        </div>
      {/each}
    </Section>
    </SectionGrid>
  </Page>
{:else if steady.error}
  <Page title="Steady order" back={chrome.phone ? undefined : { href: "/steady", label: "Steady orders" }}>
    <p class="t-quiet">Cannot read {id}: {steady.error}</p>
  </Page>
{/if}

{#snippet more(l: SteadyLine)}
  {@const flags = l.flags.filter((f) => !l.sentence.includes(f.sentence))}
  {@const chart = l.history && l.history.length > 1 && l.flags.some((f) => f.kind === "per_guest_up")}
  {#if l.split || flags.length || chart || l.orderId}
    <div class="below">
      <span class="pid"><span class="mono">{l.productId}</span>{#if l.orderId}<span>Order <a href="/ledger">{l.orderId}</a></span>{/if}</span>
      {#if l.split}
        <table class="split">
          <caption class="sr-only">How the line is split</caption>
          <tbody>
            {#each l.split.parts as p (p.productId)}
              <tr>
                <td>{nameWord(p.name)} <span class="mono t-quiet">{p.productId}</span>{#if p.onValioList}<span class="t-quiet">, on Valio's list</span>{/if}</td>
                <td class="r num">{amount(p.quantity, p.unit)}</td>
                <td class="r num">{money(p.totalCents)}</td>
              </tr>
            {/each}
            <tr class="sum-row">
              <td>Together, {money(l.split.extraCostCents)} ({l.split.extraCostPct} %) more</td>
              <td></td>
              <td class="r num">{money(l.split.totalCents)}</td>
            </tr>
          </tbody>
        </table>
      {/if}
      {#each flags as f, i (i)}
        <p class="flag">{prose(f.sentence)}</p>
      {/each}
      {#if chart && l.history}
        <Drift history={l.history} usual={l.usualQuantity} unit={l.unit} id="drift-{l.productId}" />
      {/if}
    </div>
  {/if}
{/snippet}

<style>
  .top {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem 1.5rem;
  }
  .renewed {
    font-size: var(--text-xs);
  }
  .ask {
    padding: 1rem;
    border-radius: var(--radius-card);
    border: 1px solid var(--color-border);
    background: var(--color-bg-card);
  }
  .problem {
    margin: 0;
    font-size: var(--text-sm);
  }
  .ctl {
    display: inline-flex;
    align-items: center;
    gap: 0.75rem;
  }
  .qty {
    min-width: 7.5rem;
    white-space: nowrap;
    text-align: end;
    font-size: var(--text-xs);
    color: var(--color-fg-secondary);
  }
  .sum {
    min-width: 5.5rem;
    white-space: nowrap;
    text-align: end;
    font-size: var(--text-sm);
    font-weight: 500;
  }
  .below {
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
    font-size: var(--text-xs);
  }
  .pid {
    display: flex;
    gap: 1rem;
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
    max-width: 34rem;
    border-collapse: collapse;
    font-size: var(--text-xs);
  }
  .split td {
    padding: 0.3rem 0.75rem 0.3rem 0;
  }
  .split tr + tr td {
    border-top: 1px solid color-mix(in srgb, var(--foreground) 6%, transparent);
  }
  .sum-row td {
    font-weight: 500;
  }
  .r {
    text-align: end;
    white-space: nowrap;
  }
  .flag {
    margin: 0;
    max-width: 62ch;
    color: var(--color-fg-secondary);
  }
  .act {
    display: flex;
    gap: 0.5rem;
  }
  @media (max-width: 760px) {
    .ctl {
      flex-wrap: wrap;
      justify-content: flex-end;
      gap: 0.35rem 0.6rem;
    }
    .qty,
    .sum {
      min-width: 0;
    }
  }
</style>
