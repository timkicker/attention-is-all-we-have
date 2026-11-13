<script lang="ts">
  // One request in the inbox, the whole row opens it.
  import { ChevronRight } from "@lucide/svelte";
  import type { InboxItem } from "$lib/api/types";
  import { money, time } from "$lib/format";
  import StatusBadge from "./StatusBadge.svelte";

  let { item }: { item: InboxItem } = $props();
  const href = $derived(`/requests/${item.id}`);
</script>

<a class="inbox-row" {href} id="inbox-{item.id}" data-status={item.status}>
  <div class="top">
    <StatusBadge status={item.status} />
    <span class="when num">{time(item.createdAt)}</span>
  </div>
  <div class="mid">
    <span class="text">{item.text}</span>
    {#if item.totalCents !== undefined}<span class="total num">{money(item.totalCents)}</span>{/if}
  </div>
  <p class="sentence">{item.sentence}</p>
  <ChevronRight class="chev" size={15} strokeWidth={2} aria-hidden="true" />
</a>

<style>
  .inbox-row {
    position: relative;
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
    padding: var(--space-row, 0.75rem) 2.5rem var(--space-row, 0.75rem) 1rem;
    text-decoration: none;
    color: var(--foreground);
  }
  .inbox-row:first-child {
    border-start-start-radius: var(--radius-card);
    border-start-end-radius: var(--radius-card);
  }
  .inbox-row:last-child {
    border-end-start-radius: var(--radius-card);
    border-end-end-radius: var(--radius-card);
  }
  .inbox-row:hover {
    background: color-mix(in srgb, var(--foreground) 4%, transparent);
  }
  .inbox-row:focus-visible {
    outline: 2px solid var(--ring);
    outline-offset: -2px;
  }
  .top {
    display: flex;
    align-items: center;
    gap: 0.625rem;
  }
  .when {
    font-size: var(--text-xs);
    color: color-mix(in srgb, var(--foreground) 64%, transparent);
  }
  .mid {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    align-items: baseline;
    gap: 0.25rem 1rem;
  }
  .text {
    font-size: var(--text-base);
    font-weight: 600;
  }
  .total {
    font-size: var(--text-base);
    font-weight: 600;
  }
  .sentence {
    margin: 0;
    font-size: var(--text-sm);
    line-height: 1.45;
    color: color-mix(in srgb, var(--foreground) 78%, transparent);
    max-width: 66ch;
  }
  .inbox-row :global(.chev) {
    position: absolute;
    inset-inline-end: 1rem;
    top: 50%;
    translate: 0 -50%;
    color: color-mix(in srgb, var(--foreground) 45%, transparent);
  }
</style>
