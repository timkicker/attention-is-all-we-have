<script lang="ts">
  /// Activity: everything the agent did, newest first under day heads. The
  /// filters are words with their counts, the chosen one underlined in petrol;
  /// they live in the address (?status=), so a filtered list can be linked and
  /// Back walks the filters.
  import { goto } from "$app/navigation";
  import { page } from "$app/state";
  import { api } from "$lib/api/client";
  import type { ActivityFilter } from "$lib/api/types";
  import { ActivityRow, byDay, Empty, FILTERS, isFilter, ListSection, live, Loading, LoadError, PageHead } from "$lib/v2";

  const status = $derived.by((): ActivityFilter => {
    const s = page.url.searchParams.get("status");
    return isFilter(s) ? s : "all";
  });
  // Each answer names the filter it was asked for, so a switch never shows the old filter's rows.
  const list = live(async () => {
    const s = status;
    return { status: s, ...(await api.activity(s)) };
  });
  const fresh = $derived(list.data?.status === status);

  const EMPTY: Record<ActivityFilter, string> = {
    all: "Nothing yet",
    ordered: "Nothing ordered yet",
    waiting: "Nothing waits for you",
    blocked: "Nothing blocked",
    standing: "No standing orders",
  };

  function pick(f: ActivityFilter) {
    if (f === status) return;
    void goto(f === "all" ? "/activity" : `/activity?status=${f}`, { noScroll: true, keepFocus: true });
  }
</script>

<PageHead title="Activity">
  <p class="lead">Everything your agent did, with the reason.</p>
</PageHead>

<!-- A kitchen with nothing yet gets no filters: five zeros say nothing. -->
{#if !list.data || list.data.counts.all > 0}
<div class="filters" role="group" aria-label="Show">
  {#each FILTERS as f (f.id)}
    <button type="button" id="filter-{f.id}" aria-pressed={status === f.id} onclick={() => pick(f.id)}>
      {f.label}{#if list.data}<em>{list.data.counts[f.id]}</em>{/if}
    </button>
  {/each}
</div>
{/if}

<div class="days">
  {#if list.error && !list.data}
    <LoadError detail={list.error} />
  {:else if !list.data || !fresh}
    <Loading />
  {:else if !list.data.items.length}
    <Empty
      title={EMPTY[status]}
      detail={status === "all" ? "What your agent orders shows up here." : ""}
    />
  {:else}
    {#each byDay(list.data.items) as g (g.key)}
      <section class="dg" aria-labelledby="day-{g.key}">
        <h2 class="v-h" id="day-{g.key}">{g.head}</h2>
        <ListSection id="day-{g.key}-rows">
          {#each g.items as i (i.id)}<ActivityRow item={i} />{/each}
        </ListSection>
      </section>
    {/each}
  {/if}
</div>

<style>
  .filters {
    margin-top: 32px;
  }
  @media (max-width: 760px) {
    /* One row that scrolls sideways on its own, edge to edge. */
    .filters {
      margin: 20px -16px 0;
      padding: 0 16px;
    }
    .filters button {
      flex: none;
    }
  }
  .days {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-top: 8px;
  }
  .dg {
    display: flex;
    flex-direction: column;
  }
  /* The day heads: small and quiet over the ruled list, not section titles. */
  .dg .v-h {
    min-height: 0;
    margin: 0;
    padding: 24px 0 8px;
    font-family: var(--v-sans);
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    font-weight: 600;
    color: var(--v-muted);
  }
  .dg :global(.section-card) {
    border-top-color: var(--v-line-strong);
  }
</style>
