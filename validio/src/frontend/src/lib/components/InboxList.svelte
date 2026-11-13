<script lang="ts">
  /// The list column of the inbox: one row per request, its title on one
  /// line, its state as a word (only "Waiting for you" as a badge, the one
  /// state that asks something), the total. The open request carries the
  /// kit's selection fill and nothing else.
  import type { InboxItem } from "$lib/api/types";
  import { STATUS, look, money, prose } from "$lib/format";
  import State from "./State.svelte";

  let { items, selected }: { items: InboxItem[]; selected?: string } = $props();
</script>

<ul class="list" aria-label="Requests">
  {#each items as it (it.id)}
    {@const s = look(STATUS, it.status)}
    <li>
      <a
        href="/requests/{it.id}"
        id="inbox-{it.id}"
        data-testid="inbox-{it.id}"
        class="item"
        class:on={it.id === selected}
        aria-current={it.id === selected ? "page" : undefined}
      >
        <span class="subject">{it.displayName ?? prose(it.text)}</span>
        <span class="state">
          {#if it.status === "waiting"}<State label={s.label} tone="act" />{:else}<span class:t-bad={s.tone === "bad"}>{s.label}</span>{/if}
        </span>
        <span class="total num">{money(it.totalCents)}</span>
      </a>
    </li>
  {:else}
    <li class="empty">No requests yet. The kitchen's agent sends them here.</li>
  {/each}
</ul>

<style>
  .list {
    display: flex;
    flex-direction: column;
    gap: 2px;
    margin: 0;
    padding: 0.5rem;
    list-style: none;
  }
  .item {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 0.2rem 0.75rem;
    align-items: center;
    padding: 0.55rem 0.6rem;
    border-radius: var(--radius-input);
    color: inherit;
    text-decoration: none;
    transition: background-color var(--duration-fast) var(--ease-default);
  }
  .item:hover {
    background: color-mix(in srgb, var(--color-fg-primary) 5%, transparent);
  }
  .item.on {
    background: color-mix(in srgb, var(--color-fg-primary) 10%, transparent);
  }
  .subject {
    grid-column: 1 / -1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: var(--text-sm);
    font-weight: 500;
  }
  .state {
    font-size: var(--text-xs);
    color: var(--color-fg-secondary);
  }
  .total {
    font-size: var(--text-sm);
  }
  .empty {
    padding: 1rem 0.55rem;
    font-size: var(--text-sm);
    color: var(--color-fg-secondary);
  }
</style>
