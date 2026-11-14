<script lang="ts">
  /// One timeline line, the same on Home and Activity: time, the outcome as a
  /// coloured word on a thin rule, title with the why under it, amount, and
  /// the whole row a link to its detail. Desk: one line in four columns.
  /// Phone: outcome and amount on top, then title, why and time. Put rows
  /// inside a ListSection (the ruled list).
  import type { ActivityItem } from "$lib/api/types";
  import { hm, nb, total } from "./format";
  import StatusPill from "./StatusPill.svelte";
  import { pillOf } from "./status";

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
  const tone = $derived(pillOf(item).tone);
</script>

<a class="ar" class:no-time={!showTime} {href} id="activity-{item.id}" data-testid="activity-{item.id}" data-status={item.status}>
  {#if showTime}<span class="ar-time num">{hm(item.at)}</span>{/if}
  <span class="ar-pill tone-{tone}"><StatusPill item={item} /></span>
  <span class="ar-main">
    <span class="ar-title">{nb(item.title)}</span>
    <span class="ar-why">{nb(item.why)}</span>
  </span>
  <span class="ar-end num">{nb(total(item.totalCents))}</span>
</a>

<style>
  .ar {
    display: grid;
    grid-template-columns: 56px 152px minmax(0, 1fr) auto;
    column-gap: 24px;
    align-items: baseline;
    align-content: center;
    min-height: 64px;
    padding: 14px 10px;
    color: inherit;
    text-decoration: none;
    transition: background-color var(--duration-fast) ease;
  }
  .ar.no-time {
    grid-template-columns: 152px minmax(0, 1fr) auto;
  }
  .ar:hover {
    background: var(--v-tint-hover);
  }
  .ar:hover .ar-title {
    color: var(--valio);
  }
  .ar-time {
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-faint);
  }
  /* The outcome: its word in its colour, a thin rule of the same colour before it. */
  .ar-pill {
    display: flex;
    padding-left: 10px;
    border-left: 2px solid var(--v-line-strong);
  }
  .ar-pill.tone-ok {
    border-left-color: var(--v-ok);
  }
  .ar-pill.tone-bad {
    border-left-color: var(--v-bad);
  }
  .ar-pill.tone-wait {
    border-left-color: var(--valio);
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
    transition: color var(--duration-fast) ease;
  }
  .ar-why {
    margin-top: 2px;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-muted);
  }
  .ar-end {
    font-size: var(--fs-body);
    line-height: var(--lh-body);
    white-space: nowrap;
    text-align: right;
  }
  @media (max-width: 760px) {
    .ar,
    .ar.no-time {
      grid-template-columns: minmax(0, 1fr) auto;
      row-gap: 4px;
      padding: 14px 0;
    }
    .ar-pill {
      grid-row: 1;
      grid-column: 1;
    }
    .ar-end {
      grid-row: 1;
      grid-column: 2;
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
