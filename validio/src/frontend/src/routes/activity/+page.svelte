<script lang="ts">
  /// Activity (builder A): filter chips (FILTERS, counts from the API), then
  /// the timeline under day heads. The stub lists everything so the shell's
  /// rows can be seen; the builder adds the chips and the ?status= filter.
  import { api } from "$lib/api/client";
  import { ActivityRow, byDay, Empty, ListSection, live, Loading, LoadError, PageHead } from "$lib/v2";

  const list = live(() => api.activity("all"));
</script>

<PageHead title="Activity" />

<div class="blocks">
  {#if list.error && !list.data}
    <LoadError detail={list.error} />
  {:else if !list.data}
    <Loading />
  {:else if !list.data.items.length}
    <Empty title="Nothing yet" detail="What your agent orders shows up here." />
  {:else}
    {#each byDay(list.data.items) as g (g.key)}
      <div class="dg">
        <h2 class="v-h" id="day-{g.key}">{g.head}</h2>
        <ListSection id="day-{g.key}-rows">
          {#each g.items as i (i.id)}<ActivityRow item={i} />{/each}
        </ListSection>
      </div>
    {/each}
  {/if}
</div>

<style>
  .dg {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
</style>
