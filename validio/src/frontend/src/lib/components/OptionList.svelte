<script lang="ts">
  /// Why this product: one row per option, in Validio's order. A row is the
  /// name, the total and one plain word for what happened to it, with one
  /// clause of reason under it. The product number, the amount, the facts and
  /// the supplier's own text open under the row. Only the first few rows show;
  /// "Show all" brings the rest. Rows that are not shown stay in the page, so
  /// the order on screen is always Validio's order.
  import * as Collapsible from "@arlen/ui-kit/components/ui/collapsible";
  import type { RankedOption } from "$lib/api/types";
  import { VERDICT, amount, look, money, nameWord, sentences } from "$lib/format";
  import FactTable from "./FactTable.svelte";
  import SupplierNote from "./SupplierNote.svelte";

  let { options, label, show = 3 }: { options: RankedOption[]; label: string; show?: number } = $props();

  let all = $state(false);
  // The chosen option always shows, plus the first few of the rest.
  const visible = $derived.by(() => {
    const keep = new Set(options.filter((o) => o.verdict === "chosen").map((o) => o.productId));
    for (const o of options) {
      if (keep.size >= show + (options.some((x) => x.verdict === "chosen") ? 1 : 0)) break;
      keep.add(o.productId);
    }
    return keep;
  });
  const hiddenCount = $derived(options.length - visible.size);

  const loud = (o: RankedOption) =>
    !!o.supplierText &&
    (o.supplierText.planted || (o.supplierText.reader?.flags ?? []).some((f) => f.code !== "mentions_claim"));
</script>

<ul class="options" aria-label={label}>
  {#each options as o (o.productId)}
    {@const v = look(VERDICT, o.verdict)}
    {@const said = sentences(o.sentence)}
    <li class="item" id="option-{o.productId}" data-testid="option-{o.productId}" hidden={!all && !visible.has(o.productId)}>
      <Collapsible.Root>
        <Collapsible.Trigger class="open">
          <Collapsible.Chevron />
          <span class="name">{nameWord(o.name)}</span>
          <span class="total num">{money(o.totalCents)}</span>
        </Collapsible.Trigger>
        <p class="why">
          <span class="word" class:chosen={o.verdict === "chosen"} class:bad={o.verdict === "blocked"}>{v.label}.</span>
          {said[0] ?? ""}
          {#if loud(o)}{sentences(o.supplierText?.reader?.summary)[0] ?? "Its description talks to AI agents."} Validio ignored it.{/if}
        </p>
        <Collapsible.Content forceMount>
          {#snippet child({ props, open })}
            <div {...props} class="more" hidden={!open}>
              <p class="id t-quiet">
                <span class="num">{amount(o.quantity, o.unit)}</span> · <span class="mono">{o.productId}</span>{#if o.onValioList} · on Valio's list{:else if o.isSubstitute} · not on Valio's list{/if}
              </p>
              {#if said.length > 1}
                <ul class="also">
                  {#each said.slice(1) as t, i (i)}<li>{t}</li>{/each}
                </ul>
              {/if}
              {#if o.facts.length}<FactTable facts={o.facts} />{/if}
              {#if o.supplierText}<SupplierNote text={o.supplierText} productId={o.productId} />{/if}
            </div>
          {/snippet}
        </Collapsible.Content>
      </Collapsible.Root>
    </li>
  {/each}
</ul>
{#if hiddenCount > 0}
  <button type="button" class="all" id="fold-options" aria-expanded={all} onclick={() => (all = !all)}>
    {all ? "Show fewer" : `Show all ${options.length}`}
  </button>
{/if}

<style>
  .options {
    display: flex;
    flex-direction: column;
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .item {
    padding-block: 0.5rem;
  }
  .item + .item {
    border-top: 1px solid color-mix(in srgb, var(--foreground) 7%, transparent);
  }
  /* One left edge: the chevron hangs in the gutter, so the name, the reason
     and the details all start at the same x. */
  .options :global(.open) {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 1rem;
    align-items: baseline;
    width: 100%;
    position: relative;
    text-align: start;
  }
  .options :global(.open .kit-chevron) {
    position: absolute;
    left: -1.25rem;
    top: 0.2rem;
  }
  .name {
    font-size: var(--text-sm);
    font-weight: 500;
  }
  .total {
    font-size: var(--text-sm);
    white-space: nowrap;
  }
  .why {
    margin: 0.1rem 0 0;
    max-width: 62ch;
    font-size: var(--text-sm);
    color: var(--color-fg-secondary);
  }
  .word.chosen {
    color: var(--color-fg-primary);
    font-weight: 500;
  }
  .word.bad {
    color: var(--destructive-on-tint);
  }
  .more {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    padding-top: 0.5rem;
  }
  .id {
    margin: 0;
    font-size: var(--text-xs);
  }
  .also {
    margin: 0;
    padding-inline-start: 1rem;
    font-size: var(--text-xs);
    color: var(--color-fg-secondary);
  }
  .all {
    align-self: flex-start;
    min-height: 2rem;
    padding: 0;
    font-size: var(--text-sm);
    font-weight: 500;
    color: var(--color-fg-secondary);
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  .all:hover {
    color: var(--color-fg-primary);
  }
</style>
