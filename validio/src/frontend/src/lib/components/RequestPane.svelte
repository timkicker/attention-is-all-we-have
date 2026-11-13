<script lang="ts">
  /// One request, read top down: what was asked, what Validio did in one
  /// sentence, the question if the owner has to answer, the Spend Pass it was
  /// checked against, then the options with the chosen one on top and the rest
  /// folded. Every field the API may leave out is optional here, so a new or
  /// half-finished request still renders.
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import * as Collapsible from "@arlen/ui-kit/components/ui/collapsible";
  import { Notice } from "@arlen/ui-kit/components/ui/notice";
  import type { RankedOption, RequestLine, SpendPass, SupplyRequest } from "$lib/api/types";
  import { STATUS, amount, day, dayTime, look, money, prose, requestTitle, sentences } from "$lib/format";
  import Facts from "./Facts.svelte";
  import Info from "./Info.svelte";
  import OptionList from "./OptionList.svelte";
  import SpendBar from "./SpendBar.svelte";
  import State from "./State.svelte";

  let { req, pass }: { req: SupplyRequest; pass?: SpendPass } = $props();

  const status = $derived(look(STATUS, req.status));
  const live = $derived(req.liveChecked);
  const title = $derived(requestTitle(req));
  const asking = $derived(req.status === "waiting" && !!req.orderId);
  // Waiting: the question's first sentence is the lead, its last the ask.
  // Otherwise the decision's first sentence leads and the rest folds.
  const asked = $derived(sentences(req.question));
  const said = $derived(sentences(req.decision?.sentence));
  const lead = $derived(asking && asked.length ? asked[0] : said[0]);
  const rest = $derived(asking ? [] : said.slice(1));

  const figures = $derived(
    [
      req.totalCents !== undefined ? { value: money(req.totalCents), label: "total" } : null,
      req.deliverBy ? { value: day(req.deliverBy), label: "deliver by", before: true } : null,
      { value: req.agent, label: "from", before: true },
    ].filter((f) => f !== null),
  );

  const words = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;
  const top = (opts: RankedOption[]) => opts.filter((o) => o.verdict === "chosen");
  const others = (opts: RankedOption[]) => opts.filter((o) => o.verdict !== "chosen");
</script>

{#snippet folded(label: string, id: string, opts: RankedOption[])}
  <Collapsible.Root>
    <Collapsible.Trigger class="fold" {id}>
      <Collapsible.Chevron />
      {label}
    </Collapsible.Trigger>
    <Collapsible.Content forceMount>
      {#snippet child({ props, open })}
        <div {...props} hidden={!open}>
          <OptionList options={opts} {label} />
        </div>
      {/snippet}
    </Collapsible.Content>
  </Collapsible.Root>
{/snippet}

{#snippet group(label: string, opts: RankedOption[] | undefined, mode: "open" | "fold", lead?: string)}
  {@const all = opts ?? []}
  {#if all.length}
    <section class="group" aria-label={label}>
      <h3>{label}</h3>
      {#if lead}<p class="lead">{lead}</p>{/if}
      {#if mode === "open"}
        <OptionList options={all} {label} />
      {:else}
        {#if top(all).length}<OptionList options={top(all)} {label} />{/if}
        {#if others(all).length}
          {@render folded(
            top(all).length ? `Ranked options (${others(all).length})` : `${words(others(all).length, "option", "options")}`,
            `fold-${label.toLowerCase().replaceAll(/[^a-z]+/g, "-")}`,
            others(all),
          )}
        {/if}
      {/if}
    </section>
  {/if}
{/snippet}

{#snippet line(l: RequestLine)}
  {#if l.substitutes || l.beyondList}
    {@render group("What was asked for", l.options, "open")}
    {@render group("Valio's substitutes", l.substitutes, "open")}
    {@const swap = sentences(l.swapSentence)[0]}
    {@render group("Beyond Valio's list", l.beyondList, "fold", swap && swap !== lead ? swap : undefined)}
  {:else}
    {@render group("Options", l.options, "fold")}
  {/if}
{/snippet}

<article class="pane" aria-labelledby="request-title">
  <header class="head">
    <div class="title-row">
      <h2 id="request-title">{title}</h2>
      <span data-testid="request-status"><State label={status.label} tone={status.tone} id="request-status" /></span>
    </div>
    <Facts items={figures} />
  </header>

  {#if lead}
    <p class="decision" id="decision-sentence">{lead}</p>
  {:else if !req.decision}
    <p class="decision t-quiet" id="decision-sentence">Validio is still checking this request.</p>
  {/if}
  {#if rest.length || req.decision?.ruleIds.length}
    <Collapsible.Root>
      <Collapsible.Trigger class="fold" id="fold-decision">
        <Collapsible.Chevron />
        How Validio decided
      </Collapsible.Trigger>
      <Collapsible.Content forceMount>
        {#snippet child({ props, open })}
          <div {...props} hidden={!open} class="how">
            {#each rest as t, i (i)}<p>{t}</p>{/each}
            {#if req.decision?.ruleIds.length}
              <p class="t-quiet">Rule <span class="mono" data-testid="request-rule">{req.decision.ruleIds.join(", ")}</span></p>
            {/if}
          </div>
        {/snippet}
      </Collapsible.Content>
    </Collapsible.Root>
  {/if}

  {#if asking}
    <div class="ask">
      <p id="ask-question">{asked.at(-1) ?? "Approve this order?"}</p>
      <Button href="/approve/{req.id}" id="open-approve" data-testid="open-approve">Open the approval</Button>
    </div>
  {/if}

  {#each req.simulated ?? [] as s, i (i)}
    <div class="sim" id={s.what.includes("stock-out") ? "simulated-stock-out" : `simulated-${i}`}>
      <Notice tone="neutral" text={/^simulated/i.test(s.sentence) ? prose(s.sentence) : `Simulated for the demo. ${prose(s.sentence)}`} />
    </div>
  {/each}

  {#if live}
    <p class="live">
      <span id="live-checked" data-testid="live-checked">Checked {words(live.ids, "product", "products")} live at Valio</span>
      <Info
        label="What checked live means"
        text="Stock, price and the order cut-off were asked from Valio for these {live.ids} products just now, in {live.calls} calls of at most 40. Everything else comes from Valio's catalogue."
      />
    </p>
  {/if}

  {#if pass}
    <section class="pass" aria-label="Spend Pass" data-testid="spend-pass">
      <div class="pass-head">
        <h3>Spend Pass <a class="pass-id" href="/spend-pass">{pass.id}</a></h3>
        <span class="t-quiet">held by {pass.holder}</span>
      </div>
      {#if pass.autoLimitCents !== undefined && pass.hardCapCents !== undefined}
        <SpendBar id="spend-bar" spentCents={req.totalCents ?? 0} autoLimitCents={pass.autoLimitCents} hardCapCents={pass.hardCapCents} />
      {/if}
      <dl class="grant">
        {#if pass.autoLimitCents !== undefined}
          <div data-testid="pass-auto"><dt>May order alone up to</dt><dd class="num">{money(pass.autoLimitCents)}</dd></div>
        {/if}
        {#if pass.hardCapCents !== undefined}
          <div data-testid="pass-cap"><dt>Never above</dt><dd class="num">{money(pass.hardCapCents)}</dd></div>
        {/if}
        {#if pass.diet?.length}
          <div data-testid="pass-diet"><dt>Only</dt><dd>{pass.diet.map((d) => d.replaceAll("_", " ")).join(", ")}</dd></div>
        {/if}
        {#if pass.deliverBy}
          <div data-testid="pass-deliver-by"><dt>Delivered by</dt><dd>{day(pass.deliverBy)}</dd></div>
        {/if}
        <div data-testid="pass-valid-to"><dt>Valid until</dt><dd>{dayTime(pass.validTo)}</dd></div>
        {#if pass.hidden.includes("approvers")}
          <div data-testid="pass-approvers"><dt>Who approves</dt><dd class="t-quiet">hidden from Validio</dd></div>
        {/if}
      </dl>
    </section>
  {/if}

  {#each req.lines as l (l.lineId)}
    <div class="line">
      {#if req.lines.length > 1}<h3 class="line-title">{prose(l.text)}</h3>{/if}
      {#if l.need}
        <p class="need t-quiet">
          Read as {amount(l.need.quantity, l.need.unit)} of {l.need.what}{#if l.need.diet.length}, {l.need.diet.join(", ")}{/if}
          {#if l.note}<Info label="A note on this line" text={prose(l.note)} />{/if}
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
    gap: 1.25rem;
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
  .how {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    max-width: 62ch;
    padding: 0.5rem 0 0 1.4rem;
    font-size: var(--text-sm);
    color: var(--color-fg-secondary);
  }
  .how p {
    margin: 0;
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
    max-width: 40rem;
    padding: 1rem;
    border-radius: var(--radius-card);
    border: 1px solid var(--color-border);
  }
  .pass-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 0.75rem;
    font-size: var(--text-xs);
  }
  .pass-id {
    margin-inline-start: 0.35rem;
    font-weight: 500;
    color: var(--color-fg-secondary);
  }
  .grant {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(15rem, 1fr));
    gap: 0.35rem 1.5rem;
    margin: 0;
    font-size: var(--text-sm);
  }
  .grant div {
    display: flex;
    justify-content: space-between;
    gap: 0.75rem;
    padding-block: 0.2rem;
    border-bottom: 1px solid color-mix(in srgb, var(--foreground) 6%, transparent);
  }
  .grant dt {
    color: var(--color-fg-secondary);
  }
  .grant dd {
    margin: 0;
    font-weight: 500;
    text-align: end;
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
  .pane :global(.fold) {
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
  .pane :global(.fold:hover) {
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
