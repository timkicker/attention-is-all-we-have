<script lang="ts">
  /// Options for one line as a table: product, amount, total right-aligned,
  /// state. One clause under each row says what sets it apart; the other
  /// clauses, the facts and the supplier's text open with the kit disclosure.
  /// A supplier text that talks to agents is shown at once, because ignoring
  /// it is part of the answer.
  import * as Collapsible from "@arlen/ui-kit/components/ui/collapsible";
  import type { RankedOption } from "$lib/api/types";
  import { VERDICT, amount, look, money, nameWord, sentences } from "$lib/format";
  import FactTable from "./FactTable.svelte";
  import State from "./State.svelte";
  import SupplierNote from "./SupplierNote.svelte";

  let { options, label }: { options: RankedOption[]; label: string } = $props();

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
    {@const said = sentences(o.sentence)}
    {@const inline = loud(o)}
    {@const more = o.facts.length > 0 || said.length > 1 || (!!o.supplierText && !inline)}
    <Collapsible.Root>
      <div class="item" id="option-{o.productId}" data-testid="option-{o.productId}">
        <div class="row" role="row">
          <span class="product" role="cell">
            {#if more}
              <Collapsible.Trigger class="open">
                <Collapsible.Chevron />
                <span class="name">{nameWord(o.name)}</span>
              </Collapsible.Trigger>
            {:else}
              <span class="name plain">{nameWord(o.name)}</span>
            {/if}
            <span class="id"><span class="mono">{o.productId}</span>{#if o.onValioList}<span class="tag">on Valio's list</span>{/if}</span>
          </span>
          <span class="r num" role="cell">{amount(o.quantity, o.unit)}</span>
          <span class="r num total" role="cell">{money(o.totalCents)}</span>
          <span role="cell"><State label={v.label} tone={v.tone} /></span>
        </div>
        {#if said[0]}<p class="why">{said[0]}</p>{/if}
        {#if o.supplierText && inline}
          <div class="more"><SupplierNote text={o.supplierText} productId={o.productId} /></div>
        {/if}
        {#if more}
          <Collapsible.Content forceMount>
            {#snippet child({ props, open })}
              <div {...props} class="more" hidden={!open}>
                {#if said.length > 1}
                  <ul class="also">
                    {#each said.slice(1) as t, i (i)}<li>{t}</li>{/each}
                  </ul>
                {/if}
                {#if o.facts.length}<FactTable facts={o.facts} />{/if}
                {#if o.supplierText && !inline}<SupplierNote text={o.supplierText} productId={o.productId} />{/if}
              </div>
            {/snippet}
          </Collapsible.Content>
        {/if}
      </div>
    </Collapsible.Root>
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
    border-bottom: 1px solid color-mix(in srgb, var(--foreground) 6%, transparent);
  }
  .r {
    text-align: end;
  }
  .product {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }
  .options :global(.open) {
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
  .options :global(.open:hover .name) {
    text-decoration: underline;
    text-underline-offset: 3px;
    text-decoration-color: var(--color-fg-secondary);
  }
  .name.plain {
    padding-inline-start: 1.2rem;
  }
  .options :global(.kit-chevron) {
    width: 0.9rem;
    padding-top: 0.2rem;
    color: var(--color-fg-secondary);
  }
  .name {
    font-size: var(--text-sm);
    font-weight: 500;
    overflow-wrap: normal;
    hyphens: manual;
  }
  .id {
    padding-inline-start: 1.2rem;
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
    padding-inline-start: 1.2rem;
    max-width: 62ch;
    font-size: var(--text-xs);
    color: var(--color-fg-secondary);
  }
  .also {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
    margin: 0;
    padding: 0;
    list-style: none;
    font-size: var(--text-xs);
    color: var(--color-fg-secondary);
  }
  .more:not([hidden]) {
    display: flex;
    flex-direction: column;
    gap: 0.9rem;
    margin-top: 0.7rem;
    padding: 0.75rem 0 0.25rem 1.2rem;
    border-top: 1px solid color-mix(in srgb, var(--foreground) 10%, transparent);
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
