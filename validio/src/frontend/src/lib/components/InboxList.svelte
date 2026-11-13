<script lang="ts">
  /// The list column of the inbox, as Arlen mail draws its message list: the
  /// request as the subject, the total on the right, its state and time under
  /// it, and Validio's sentence as the snippet.
  import type { InboxItem } from "$lib/api/types";
  import { STATUS, look, money, time } from "$lib/format";

  let { items, selected }: { items: InboxItem[]; selected?: string } = $props();
</script>

<ul class="list" aria-label="Requests">
  {#each items as it (it.id)}
    {@const s = look(STATUS, it.status)}
    <li>
      <a
        href="/requests/{it.id}"
        id="inbox-{it.id}"
        class="item"
        class:on={it.id === selected}
        aria-current={it.id === selected ? "page" : undefined}
      >
        <span class="top">
          <span class="subject">{it.text}</span>
          <span class="total num">{money(it.totalCents)}</span>
        </span>
        <span class="meta">
          <span class="state t-{s.tone}">{#if s.tone === "act"}<span class="dot" aria-hidden="true"></span>{/if}{s.label}</span>
          <span class="time num">{time(it.createdAt).slice(0, 5)}</span>
        </span>
        <span class="snippet">{it.sentence}</span>
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
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
    padding: 0.5rem 0.55rem;
    border-radius: var(--radius-input);
    border: 1px solid transparent;
    color: inherit;
    text-decoration: none;
    transition: background-color var(--duration-fast) var(--ease-default);
  }
  .item:hover {
    background: color-mix(in srgb, var(--color-fg-primary) 5%, transparent);
  }
  .item.on {
    background: color-mix(in srgb, var(--color-fg-primary) 9%, transparent);
    border-color: var(--v-select);
  }
  .top,
  .meta {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 0.75rem;
  }
  .subject {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: var(--text-sm);
    font-weight: 500;
  }
  .total {
    flex-shrink: 0;
    font-size: var(--text-sm);
  }
  .meta {
    font-size: var(--text-2xs);
  }
  .state {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    font-weight: 500;
  }
  .state.t-act {
    color: var(--color-fg-primary);
  }
  .dot {
    width: 0.4rem;
    height: 0.4rem;
    border-radius: var(--radius-chip);
    background: var(--color-fg-primary);
  }
  .time {
    color: var(--color-fg-secondary);
  }
  .snippet {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: var(--text-xs);
    color: color-mix(in srgb, var(--color-fg-primary) 50%, transparent);
  }
  .empty {
    padding: 1rem 0.55rem;
    font-size: var(--text-sm);
    color: var(--color-fg-secondary);
  }
</style>
