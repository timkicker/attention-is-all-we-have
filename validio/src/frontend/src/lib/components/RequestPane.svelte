<script lang="ts">
  /// One request, read top down: what happened, why, and the evidence folded
  /// away. Every field the API may leave out is optional here, so a new or
  /// half-finished request still renders.
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import * as Collapsible from "@arlen/ui-kit/components/ui/collapsible";
  import { Notice } from "@arlen/ui-kit/components/ui/notice";
  import type { RankedOption, RequestLine, SpendPass, SupplyRequest } from "$lib/api/types";
  import { STATUS, amount, day, look, money } from "$lib/format";
  import Facts from "./Facts.svelte";
  import Info from "./Info.svelte";
  import OptionList from "./OptionList.svelte";
  import SpendBar from "./SpendBar.svelte";
  import State from "./State.svelte";

  let { req, pass }: { req: SupplyRequest; pass?: SpendPass } = $props();

  const status = $derived(look(STATUS, req.status));
  const live = $derived(req.liveChecked);

  const figures = $derived(
    [
      req.totalCents !== undefined ? { value: money(req.totalCents), label: "total" } : null,
      req.deliverBy ? { value: day(req.deliverBy), label: "deliver by", before: true } : null,
      { value: req.agent, label: "from", before: true },
    ].filter((f) => f !== null),
  );

  const split = (opts: RankedOption[] | undefined) => {
    const all = opts ?? [];
    return { shown: all.filter((o) => o.verdict !== "rejected"), turned: all.filter((o) => o.verdict === "rejected") };
  };

  const words = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;
</script>

{#snippet group(label: string, opts: RankedOption[] | undefined, lead?: string)}
  {@const g = split(opts)}
  {#if g.shown.length || g.turned.length}
    <section class="group" aria-label={label}>
      <h3>{label}</h3>
      {#if lead}<p class="lead">{lead}</p>{/if}
      {#if g.shown.length}<OptionList options={g.shown} {label} />{/if}
      {#if g.turned.length}
        <Collapsible.Root>
          <Collapsible.Trigger class="fold" id="fold-{label.toLowerCase().replaceAll(/[^a-z]+/g, '-')}">
            <Collapsible.Chevron />
            {words(g.turned.length, "more turned down", "more turned down")}
          </Collapsible.Trigger>
          <Collapsible.Content>
            <OptionList options={g.turned} label="{label}, turned down" />
          </Collapsible.Content>
        </Collapsible.Root>
      {/if}
    </section>
  {/if}
{/snippet}

{#snippet line(l: RequestLine)}
  {#if l.substitutes || l.beyondList}
    {@render group("What was asked for", l.options)}
    {@render group("Valio's substitutes", l.substitutes)}
    {@render group("Beyond Valio's list", l.beyondList, l.swapSentence)}
  {:else}
    {@render group("Options", l.options)}
  {/if}
{/snippet}

<article class="pane" aria-labelledby="request-title">
  <header class="head">
    <div class="title-row">
      <h2 id="request-title">{req.text}</h2>
      <State label={status.label} tone={status.tone} id="request-status" />
    </div>
    <Facts items={figures} />
  </header>

  {#if req.decision}
    <p class="decision" id="decision-sentence">{req.decision.sentence}</p>
  {:else}
    <p class="decision t-quiet" id="decision-sentence">Validio is still checking this request.</p>
  {/if}

  {#if req.status === "waiting" && req.orderId}
    <div class="ask">
      {#if req.question}<p id="ask-question">{req.question}</p>{/if}
      <Button href="/approve/{req.orderId}" id="open-approve">Open the approval</Button>
    </div>
  {/if}

  {#each req.simulated ?? [] as s, i (i)}
    <div class="sim" id={s.what.includes("stock-out") ? "simulated-stock-out" : `simulated-${i}`}>
      <Notice tone="neutral" text="Simulated, only in this demo. {s.sentence}" />
    </div>
  {/each}

  {#if live}
    <p class="live">
      <span id="live-checked">Checked {words(live.ids, "product", "products")} live at Valio</span>
      <span class="t-quiet">in {words(live.calls, "call", "calls")}</span>
      <Info
        label="What checked live means"
        text="Stock, price and the order cut-off were asked from Valio for these products just now, at most 40 per call. Everything else comes from Valio's catalogue."
      />
    </p>
  {/if}

  {#if pass && pass.autoLimitCents !== undefined && pass.hardCapCents !== undefined}
    <section class="pass" aria-label="Spend Pass">
      <h3>Spend Pass <a class="mono pass-id" href="/spend-pass">{pass.id}</a></h3>
      <SpendBar id="spend-pass" spentCents={req.totalCents ?? 0} autoLimitCents={pass.autoLimitCents} hardCapCents={pass.hardCapCents} />
    </section>
  {/if}

  {#each req.lines as l (l.lineId)}
    <div class="line">
      {#if req.lines.length > 1}<h3 class="line-title">{l.text}</h3>{/if}
      {#if l.need}
        <p class="need t-quiet">
          Read as {amount(l.need.quantity, l.need.unit)} of {l.need.what}{#if l.need.diet.length}, {l.need.diet.join(", ")}{/if}
          {#if l.note}<Info label="A note on this line" text={l.note} />{/if}
        </p>
      {/if}
      {@render line(l)}
    </div>
  {/each}
</article>

<style>
  .pane {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
    max-width: 52rem;
    padding: 1.5rem 1.75rem 3rem;
  }
  .head {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .title-row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem 0.75rem;
  }
  h2 {
    margin: 0;
    font-size: var(--text-lg);
    font-weight: 600;
    line-height: 1.3;
  }
  h3 {
    margin: 0;
    font-size: var(--text-sm);
    font-weight: 600;
  }
  .decision {
    margin: 0;
    max-width: 62ch;
    font-size: var(--text-base);
    line-height: 1.55;
  }
  .ask {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 0.75rem;
    padding: 1rem;
    border-radius: var(--radius-card);
    border: 1px solid var(--color-border);
    background: var(--color-bg-card);
  }
  .ask p {
    margin: 0;
    max-width: 62ch;
    font-size: var(--text-sm);
  }
  .live {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.25rem 0.5rem;
    margin: 0;
    font-size: var(--text-sm);
  }
  .pass {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    max-width: 36rem;
  }
  .pass-id {
    margin-inline-start: 0.35rem;
    font-size: var(--text-xs);
    font-weight: 400;
    color: var(--color-fg-secondary);
  }
  .line {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }
  .need {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    margin: 0;
    font-size: var(--text-sm);
  }
  .group {
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
  }
  .lead {
    margin: 0;
    max-width: 62ch;
    font-size: var(--text-sm);
    color: var(--color-fg-secondary);
  }
  :global(.fold) {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    margin-top: 0.25rem;
    padding: 0.25rem 0.4rem;
    border-radius: var(--radius-input);
    font-size: var(--text-xs);
    font-weight: 500;
    color: var(--color-fg-secondary);
  }
  :global(.fold:hover) {
    background: color-mix(in srgb, var(--color-fg-primary) 6%, transparent);
    color: var(--color-fg-primary);
  }
  @media (max-width: 760px) {
    .pane {
      padding: 1rem 1rem 2rem;
      gap: 1.25rem;
    }
  }
</style>
