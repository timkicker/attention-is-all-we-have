<script lang="ts">
  /// Options for one line as a table: product, amount, total right-aligned,
  /// state. The reason sits under each row in one sentence; the facts and the
  /// supplier's text open on demand. A supplier text that talks to agents is
  /// shown at once, because ignoring it is part of the answer.
  import { ChevronRight } from "@lucide/svelte";
  import type { RankedOption } from "$lib/api/types";
  import { VERDICT, amount, look, money } from "$lib/format";
  import FactTable from "./FactTable.svelte";
  import State from "./State.svelte";
  import SupplierNote from "./SupplierNote.svelte";

  let { options, label }: { options: RankedOption[]; label: string } = $props();

  let open = $state<Record<string, boolean>>({});

  const loud = (o: RankedOption) =>
    !!o.supplierText &&
    (o.supplierText.planted || (o.supplierText.reader?.flags ?? []).some((f) => f.code !== "mentions_claim"));
</script>

<div class="options" role="table" aria-label={label}>
  <div class="row head" role="row">
    <span role="columnheader">Product</span>
    <span role="columnheader" class="r">Amount</span>
    <span role="columnheader" class="r">Total</span>
    <span role="columnheader">State</span>
  </div>
  {#each options as o (o.productId)}
    {@const v = look(VERDICT, o.verdict)}
    {@const more = o.facts.length > 0 || !!o.supplierText}
    <div class="item" id="option-{o.productId}" class:chosen={o.verdict === "chosen"}>
      <div class="row" role="row">
        <span class="product" role="cell">
          {#if more}
            <button
              type="button"
              class="open"
              aria-expanded={!!open[o.productId]}
              aria-controls="more-{o.productId}"
              onclick={() => (open[o.productId] = !open[o.productId])}
            >
              <span class="chev" class:on={open[o.productId]}><ChevronRight size={14} strokeWidth={2} /></span>
              <span class="name">{o.name}</span>
            </button>
          {:else}
            <span class="name plain">{o.name}</span>
          {/if}
          <span class="id mono">{o.productId}{#if o.onValioList}<span class="tag">on Valio's list</span>{/if}</span>
        </span>
        <span class="r num" role="cell">{amount(o.quantity, o.unit)}</span>
        <span class="r num total" role="cell">{money(o.totalCents)}</span>
        <span role="cell"><State label={v.label} tone={v.tone} /></span>
      </div>
      <p class="why">{o.sentence}</p>
      {#if o.supplierText && loud(o) && !open[o.productId]}
        <div class="more"><SupplierNote text={o.supplierText} productId={o.productId} /></div>
      {/if}
      {#if open[o.productId]}
        <div class="more" id="more-{o.productId}">
          {#if o.facts.length}<FactTable facts={o.facts} />{/if}
          {#if o.supplierText}<SupplierNote text={o.supplierText} productId={o.productId} />{/if}
        </div>
      {/if}
    </div>
  {/each}
</div>

<style>
  .options {
    display: flex;
    flex-direction: column;
  }
  .row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 7.5rem 7rem 7.6rem;
    gap: 0.75rem;
    align-items: center;
  }
  .head {
    padding: 0 0.6rem 0.4rem;
    font-size: var(--text-2xs);
    font-weight: 500;
    color: var(--color-fg-secondary);
    border-bottom: 1px solid var(--color-border);
  }
  .item {
    padding: 0.55rem 0.6rem;
    border-radius: var(--radius-input);
    border: 1px solid transparent;
  }
  .item + .item {
    margin-top: 1px;
  }
  .item:not(:last-child) {
    box-shadow: 0 1px 0 color-mix(in srgb, var(--foreground) 6%, transparent);
  }
  .item.chosen {
    border-color: var(--v-select);
    box-shadow: none;
  }
  .r {
    text-align: end;
  }
  .product {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }
  .open {
    display: flex;
    align-items: flex-start;
    gap: 0.3rem;
    padding: 0;
    text-align: start;
    font: inherit;
    color: inherit;
    background: none;
    border: 0;
    cursor: pointer;
  }
  .open:hover .name {
    text-decoration: underline;
    text-underline-offset: 3px;
    text-decoration-color: var(--color-fg-secondary);
  }
  .chev {
    display: inline-flex;
    width: 0.95rem;
    padding-top: 0.2rem;
    color: var(--color-fg-secondary);
    transition: rotate var(--duration-normal) var(--ease-out);
  }
  .chev.on {
    rotate: 90deg;
  }
  .name.plain {
    padding-inline-start: 1.25rem;
  }
  .name {
    font-size: var(--text-sm);
    font-weight: 500;
  }
  .id {
    padding-inline-start: 1.25rem;
    font-size: var(--text-2xs);
    color: var(--color-fg-secondary);
  }
  .tag {
    margin-inline-start: 0.6rem;
    font-family: var(--font-sans);
  }
  .total {
    font-weight: 500;
  }
  .why {
    margin: 0.2rem 0 0;
    padding-inline-start: 1.25rem;
    max-width: 62ch;
    font-size: var(--text-xs);
    color: var(--color-fg-secondary);
  }
  .more {
    display: flex;
    flex-direction: column;
    gap: 0.9rem;
    margin-top: 0.7rem;
    padding: 0.75rem 0 0.25rem 1.25rem;
    border-top: 1px solid color-mix(in srgb, var(--foreground) 10%, transparent);
  }
  @media (prefers-reduced-motion: reduce) {
    .chev {
      transition: none;
    }
  }
  @media (max-width: 760px) {
    .head {
      display: none;
    }
    .row {
      grid-template-columns: 1fr auto;
      gap: 0.25rem 0.75rem;
    }
    .product {
      grid-column: 1 / -1;
    }
    .row > :nth-child(2) {
      text-align: start;
      color: var(--color-fg-secondary);
    }
    .row > :nth-child(3) {
      grid-row: 2;
      grid-column: 2;
    }
    .row > :nth-child(4) {
      grid-column: 1 / -1;
    }
  }
</style>
