<script lang="ts">
  /// One timeline line, the same on Home and Activity: time, status pill, title
  /// with the why under it, amount, and the whole row a link to its detail.
  /// Desk: one line in four columns. Phone: pill and amount on top, then title,
  /// why and time. Put rows inside a ListSection (the kit Section card).
  import { ChevronRight } from "@lucide/svelte";
  import type { ActivityItem } from "$lib/api/types";
  import { hm, nb, total } from "./format";
  import StatusPill from "./StatusPill.svelte";

  let {
    item,
    href = `/activity/${encodeURIComponent(item.id)}`,
    showTime = true,
  }: {
    item: ActivityItem;
    /** Defaults to the item's detail page. */
    href?: string;
    showTime?: boolean;
  } = $props();
</script>

<a class="ar" class:no-time={!showTime} {href} id="activity-{item.id}" data-testid="activity-{item.id}" data-status={item.status}>
  {#if showTime}<span class="ar-time">{hm(item.at)}</span>{/if}
  <span class="ar-pill"><StatusPill status={item.status} /></span>
  <span class="ar-main">
    <span class="ar-title">{nb(item.title)}</span>
    <span class="ar-why">{nb(item.why)}</span>
  </span>
  <span class="ar-end">
    <span class="num">{nb(total(item.totalCents))}</span>
    <ChevronRight class="go" size={16} strokeWidth={1.75} aria-hidden="true" />
  </span>
</a>

<style>
  .ar {
    display: grid;
    grid-template-columns: 48px 128px minmax(0, 1fr) auto;
    column-gap: 12px;
    align-items: baseline;
    align-content: center;
    min-height: 64px;
    padding: 12px 16px;
    color: inherit;
    text-decoration: none;
    transition: background-color var(--duration-fast) ease;
  }
  .ar.no-time {
    grid-template-columns: 128px minmax(0, 1fr) auto;
  }
  .ar:hover {
    background: var(--v-tint-hover);
  }
  /* In a card the first and last row keep the card's inner corner. */
  :global(.section-card) > .ar:first-child {
    border-start-start-radius: max(0px, calc(var(--radius-card) - 1px));
    border-start-end-radius: max(0px, calc(var(--radius-card) - 1px));
  }
  :global(.section-card) > .ar:last-child {
    border-end-start-radius: max(0px, calc(var(--radius-card) - 1px));
    border-end-end-radius: max(0px, calc(var(--radius-card) - 1px));
  }
  .ar-time {
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-faint);
    font-variant-numeric: tabular-nums;
  }
  .ar-pill {
    display: flex;
  }
  .ar-main {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }
  .ar-title {
    font-size: var(--fs-body);
    line-height: var(--lh-body);
    font-weight: 500;
    overflow-wrap: anywhere;
  }
  .ar-why {
    margin-top: 2px;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-muted);
  }
  .ar-end {
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: var(--fs-body);
    line-height: var(--lh-body);
    font-weight: 500;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  .ar-end :global(.go) {
    color: var(--v-faint);
    flex: none;
  }
  @media (max-width: 760px) {
    .ar,
    .ar.no-time {
      grid-template-columns: minmax(0, 1fr) auto;
      row-gap: 4px;
      padding: 12px 16px;
    }
    .ar-pill {
      grid-row: 1;
      grid-column: 1;
    }
    .ar-end {
      grid-row: 1;
      grid-column: 2;
    }
    .ar-end :global(.go) {
      display: none;
    }
    .ar-main {
      grid-column: 1 / -1;
    }
    .ar-time {
      grid-row: 3;
      grid-column: 1 / -1;
    }
  }
</style>
