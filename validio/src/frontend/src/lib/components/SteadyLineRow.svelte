<script lang="ts">
  // One line of a Steady Order: usual against this week, what renewal did and
  // the Drift Watch flags that hold it.
  import { Badge } from "@arlen/ui-kit/components/ui/badge";
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import { TriangleAlert } from "@lucide/svelte";
  import type { SteadyLine } from "$lib/api/types";
  import { LINE_RESULT, money } from "$lib/format";
  import HistoryBars from "./HistoryBars.svelte";

  let { line, onaccept, busy = false }: { line: SteadyLine; onaccept?: () => void; busy?: boolean } = $props();
  const r = $derived(LINE_RESULT[line.result]);
</script>

<div class="line" id="line-{line.productId}" data-result={line.result}>
  <div class="head">
    <div class="name">
      <span class="title">{line.name}</span>
      <span class="pid num">{line.productId}</span>
    </div>
    <div class="side">
      {#if line.totalCents !== undefined}<span class="total num">{money(line.totalCents)}</span>{/if}
      {#if line.result !== "pending"}<Badge variant={r.variant}>{r.label}</Badge>{/if}
    </div>
  </div>
  <div class="amounts num">
    Usual {line.usualQuantity} {line.unit}{#if line.thisWeekQuantity !== undefined}, this week {line.thisWeekQuantity} {line.unit}{/if}
  </div>
  <p class="sentence">{line.sentence}</p>

  {#if line.split}
    <ul class="split" aria-label="Split">
      {#each line.split.parts as part (part.productId)}
        <li>
          <span class="num">{part.quantity} {part.unit}</span>
          <span>{part.productId} {part.name}{part.onValioList ? ", from Valio's substitute list" : ""}</span>
          <span class="num part-total">{money(part.totalCents)}</span>
        </li>
      {/each}
    </ul>
  {/if}

  {#each line.flags as flag (flag.kind)}
    <div class="flag" data-flag={flag.kind}>
      <TriangleAlert size={14} strokeWidth={2} aria-hidden="true" />
      <div class="flag-body">
        <p>{flag.sentence}</p>
        {#if flag.kind === "per_guest_up" && line.history}
          <HistoryBars weeks={line.history} unit={line.unit} label="{line.name}, {line.unit} per week" />
        {/if}
      </div>
    </div>
  {/each}

  {#if line.acceptLabel && onaccept}
    <div class="act">
      <Button id="accept-{line.productId}" size="sm" disabled={busy} onclick={onaccept}>{line.acceptLabel}</Button>
    </div>
  {/if}
</div>

<style>
  .line {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
    padding: var(--space-row, 0.75rem) 1rem;
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
  }
  .title {
    font-size: var(--text-base);
    font-weight: 600;
  }
  .pid,
  .amounts {
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
  }
  .sentence {
    margin: 0;
    font-size: var(--text-sm);
    line-height: 1.45;
    max-width: 64ch;
  }
  .split {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    margin: 0;
    padding: 0.5rem 0.75rem;
    list-style: none;
    border-radius: calc(var(--radius-card) - var(--space-row, 0.75rem) / 2);
    background: color-mix(in srgb, var(--foreground) 4%, transparent);
    font-size: var(--text-xs);
  }
  .split li {
    display: grid;
    grid-template-columns: 5.5rem 1fr auto;
    gap: 0.75rem;
  }
  .part-total {
    text-align: end;
  }
  .flag {
    display: flex;
    gap: 0.55rem;
    padding: 0.625rem 0.75rem;
    border-radius: calc(var(--radius-card) - var(--space-row, 0.75rem) / 2);
    border: 1px solid color-mix(in srgb, var(--color-warning) 40%, transparent);
    background: color-mix(in srgb, var(--color-warning) 7%, transparent);
    font-size: var(--text-sm);
    line-height: 1.45;
  }
  .flag :global(svg) {
    flex-shrink: 0;
    margin-top: 0.2rem;
    color: var(--color-warning);
  }
  .flag-body {
    display: flex;
    flex-direction: column;
    gap: 0.625rem;
  }
  .flag p {
    margin: 0;
  }
  .act {
    padding-top: 0.25rem;
  }
  @media (max-width: 480px) {
    .split li {
      grid-template-columns: 1fr auto;
    }
    .split li > :nth-child(2) {
      grid-column: 1 / -1;
      grid-row: 2;
      color: color-mix(in srgb, var(--foreground) 72%, transparent);
    }
  }
</style>
