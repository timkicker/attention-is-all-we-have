<script lang="ts">
  /// The list column of the inbox, as Arlen mail draws its message list: the
  /// request as the subject, the total on the right, its state and time under
  /// it, and Validio's first sentence as the snippet. The open request carries
  /// the kit's selection fill and nothing else.
  import type { InboxItem } from "$lib/api/types";
  import { STATUS, look, money, prose, sentences, time } from "$lib/format";
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
        <span class="top">
          <span class="subject">{it.displayName ?? prose(it.text)}</span>
          <span class="total num">{money(it.totalCents)}</span>
        </span>
        <span class="meta">
          <State label={s.label} tone={s.tone} />
          <span class="time num">{time(it.createdAt)}</span>
        </span>
        <span class="snippet">{sentences(it.sentence)[0] ?? ""}</span>
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
    gap: 0.25rem;
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
  .top,
  .meta {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
  }
  .subject {
    min-width: 0;
    font-size: var(--text-sm);
    font-weight: 500;
    line-height: 1.35;
  }
  .total {
    flex-shrink: 0;
    align-self: baseline;
    font-size: var(--text-sm);
  }
  .time {
    font-size: var(--text-2xs);
    color: var(--color-fg-secondary);
  }
  .snippet {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    font-size: var(--text-xs);
    color: var(--color-fg-secondary);
  }
  .empty {
    padding: 1rem 0.55rem;
    font-size: var(--text-sm);
    color: var(--color-fg-secondary);
  }
</style>
