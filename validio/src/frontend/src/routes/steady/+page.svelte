<script lang="ts">
  // The kitchen's standing orders, one plain row each: the name, when it
  // runs, and whether it needs a look this week.
  import { ChevronRight } from "@lucide/svelte";
  import { api } from "$lib/api/client";
  import { setChrome } from "$lib/chrome.svelte";
  import { live } from "$lib/live.svelte";
  import Frame from "$lib/components/Frame.svelte";
  import State from "$lib/components/State.svelte";

  setChrome("Steady orders");
  const list = live(() => api.steadyList());
</script>

<Frame title="Steady orders" top>
  {#if list.data}
    <ul class="rows">
      {#each list.data as s (s.id)}
        <li>
          <a class="row" href="/steady/{s.id}" id="steady-{s.id}" data-testid="steady-{s.id}">
            <span class="name">{s.name}</span>
            <span class="when">Every {s.weekday}</span>
            <span class="state">
              {#if s.flagCount}<State label="{s.flagCount} need a look" tone="act" />
              {:else if s.renewedAt}Renewed{:else}Not renewed yet{/if}
            </span>
            <ChevronRight size={16} strokeWidth={1.75} aria-hidden="true" />
          </a>
        </li>
      {:else}
        <li class="t-quiet">No steady orders yet.</li>
      {/each}
    </ul>
  {:else if list.error}
    <p class="t-quiet">Cannot read the steady orders: {list.error}</p>
  {/if}
</Frame>

<style>
  .rows {
    margin: 0;
    padding: 0;
    list-style: none;
  }
  li + li {
    border-top: 1px solid color-mix(in srgb, var(--foreground) 7%, transparent);
  }
  .row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto auto 1rem;
    gap: 1rem;
    align-items: center;
    min-height: 2.75rem;
    padding: 0.5rem 0.35rem;
    border-radius: var(--radius-input);
    color: inherit;
    text-decoration: none;
  }
  .row:hover {
    background: color-mix(in srgb, var(--color-fg-primary) 5%, transparent);
  }
  .name {
    font-size: var(--text-sm);
    font-weight: 500;
  }
  .when,
  .state {
    font-size: var(--text-sm);
    color: var(--color-fg-secondary);
  }
  .row :global(svg) {
    color: var(--color-fg-secondary);
  }
  @media (max-width: 760px) {
    .row {
      grid-template-columns: minmax(0, 1fr) 1rem;
      gap: 0.15rem 0.75rem;
    }
    .when,
    .state {
      grid-column: 1;
    }
    .row :global(svg) {
      grid-column: 2;
      grid-row: 1 / span 3;
    }
  }
</style>
