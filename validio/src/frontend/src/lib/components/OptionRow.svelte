<script lang="ts">
  // One option for a request line: its place in the ranking, the sentence why
  // it won or lost, the total and the facts behind it. Sits in a Section card
  // with the same inset as the kit's Row.
  import { Badge } from "@arlen/ui-kit/components/ui/badge";
  import * as Collapsible from "@arlen/ui-kit/components/ui/collapsible";
  import type { RankedOption } from "$lib/api/types";
  import { VERDICT, money } from "$lib/format";
  import FactList from "./FactList.svelte";

  let { option, open = false }: { option: RankedOption; open?: boolean } = $props();
  const v = $derived(VERDICT[option.verdict]);
  const out = $derived(option.verdict === "rejected" || option.verdict === "blocked" || option.verdict === "not_deliverable");
  let expanded = $state(false);
  $effect(() => {
    expanded = open;
  });
</script>

<div class="option" class:out class:unranked={option.rank === undefined} id="option-{option.productId}" data-verdict={option.verdict}>
  <div class="rank num" aria-hidden={option.rank === undefined}>
    {option.rank ?? ""}
  </div>
  <div class="body">
    <div class="head">
      <div class="name">
        <span class="title">{option.name}</span>
        <span class="pid num">{option.productId}</span>
      </div>
      <div class="side">
        {#if option.totalCents !== undefined}
          <span class="total num">{money(option.totalCents)}</span>
        {/if}
        <Badge variant={v.variant}>{v.label}</Badge>
      </div>
    </div>
    {#if option.quantity}
      <div class="amount num">{option.quantity} {option.unit}{option.onValioList === false ? ", outside Valio's substitute list" : option.onValioList ? ", on Valio's substitute list" : ""}</div>
    {/if}
    <p class="sentence">{option.sentence}</p>

    {#if option.supplierText}
      <div class="supplier" id="supplier-{option.productId}">
        <div class="supplier-head">
          <span>Supplier text</span>
          <Badge variant="outline">Untrusted</Badge>
          {#if option.supplierText.planted}
            <Badge variant="warn">Planted by the team for this demo</Badge>
          {/if}
        </div>
        <blockquote>{option.supplierText.text}</blockquote>
        {#if option.supplierText.reader}
          <p class="reader">{option.supplierText.reader.note}</p>
        {/if}
      </div>
    {/if}

    {#if option.facts.length}
      <Collapsible.Root bind:open={expanded}>
        <Collapsible.Trigger class="facts-toggle" id="facts-{option.productId}">
          <Collapsible.Chevron size={13} />
          {option.facts.length === 1 ? "1 fact" : `${option.facts.length} facts`}
        </Collapsible.Trigger>
        <Collapsible.Content>
          <div class="facts"><FactList facts={option.facts} /></div>
        </Collapsible.Content>
      </Collapsible.Root>
    {/if}
  </div>
</div>

<style>
  .option {
    display: grid;
    grid-template-columns: 1.5rem 1fr;
    gap: 0.75rem;
    padding: var(--space-row, 0.75rem) 1rem;
  }
  @media (max-width: 480px) {
    .option.unranked {
      grid-template-columns: 1fr;
    }
    .option.unranked .rank {
      display: none;
    }
  }
  .rank {
    font-size: var(--text-lg);
    font-weight: 600;
    line-height: 1.2;
    color: var(--foreground);
  }
  .body {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
    min-width: 0;
  }
  .head {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    justify-content: space-between;
    gap: 0.25rem 1rem;
  }
  .name {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 0.5rem;
    min-width: 0;
  }
  .title {
    font-size: var(--text-base);
    font-weight: 600;
    color: var(--foreground);
  }
  .pid,
  .amount {
    font-size: var(--text-xs);
    color: color-mix(in srgb, var(--foreground) 64%, transparent);
  }
  .side {
    display: flex;
    align-items: center;
    gap: 0.625rem;
  }
  .total {
    font-size: var(--text-base);
    font-weight: 600;
    color: var(--foreground);
  }
  .out .title,
  .out .total {
    color: color-mix(in srgb, var(--foreground) 72%, transparent);
    font-weight: 500;
  }
  .out .rank {
    color: transparent;
  }
  .sentence {
    margin: 0;
    font-size: var(--text-sm);
    line-height: 1.45;
    color: var(--foreground);
    max-width: 62ch;
  }
  .supplier {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
    padding: 0.625rem 0.75rem;
    border-radius: calc(var(--radius-card) - var(--space-row, 0.75rem) / 2);
    border: 1px dashed color-mix(in srgb, var(--foreground) 22%, transparent);
    font-size: var(--text-xs);
  }
  .supplier-head {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
    color: color-mix(in srgb, var(--foreground) 64%, transparent);
  }
  blockquote {
    margin: 0;
    font-size: var(--text-sm);
    color: var(--foreground);
    text-decoration: line-through;
    text-decoration-color: color-mix(in srgb, var(--color-error) 70%, transparent);
  }
  .reader {
    margin: 0;
    color: color-mix(in srgb, var(--foreground) 72%, transparent);
  }
  .facts {
    padding-block: 0.25rem 0.125rem;
  }
</style>
