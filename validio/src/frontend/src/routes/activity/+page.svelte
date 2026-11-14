<script lang="ts">
  /// Activity: everything the agent did, newest first under day heads. The
  /// filter chips carry their counts and live in the address (?status=), so a
  /// filtered list can be linked and Back walks the filters.
  import { goto } from "$app/navigation";
  import { page } from "$app/state";
  import { Chip } from "@arlen/ui-kit/components/ui/chip";
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
  {#snippet facts()}<span>Everything your agent did, with the reason</span>{/snippet}
</PageHead>

<!-- A kitchen with nothing yet gets no filters: five zeros say nothing. -->
{#if !list.data || list.data.counts.all > 0}
<div class="filters" role="group" aria-label="Show">
  {#each FILTERS as f (f.id)}
    <Chip
      id="filter-{f.id}"
      label={f.label}
      meta={list.data ? String(list.data.counts[f.id]) : undefined}
      pressed={status === f.id}
      onclick={() => pick(f.id)}
    />
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
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 24px;
  }
  @media (max-width: 760px) {
    /* One row that scrolls sideways on its own, edge to edge, not two rows.
       The chips stay the kit's size; their press area reaches the 44 px a
       finger needs without moving the row. */
    .filters {
      flex-wrap: nowrap;
      overflow-x: auto;
      scrollbar-width: none;
      margin: 12px -16px 0;
      padding: 10px 16px;
    }
    .filters :global(.chip) {
      flex: none;
    }
    .filters :global(button.chip-body) {
      position: relative;
    }
    .filters :global(button.chip-body)::after {
      content: "";
      position: absolute;
      inset: -10px -4px;
    }
  }
  .days {
    display: flex;
    flex-direction: column;
    gap: 24px;
    margin-top: 24px;
  }
  .dg {
    display: flex;
    flex-direction: column;
  }
  .dg .v-h {
    margin: 0;
  }
  @media (max-width: 760px) {
    .days {
      margin-top: 14px;
    }
  }
</style>
