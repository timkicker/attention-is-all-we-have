<script lang="ts">
  // The kitchen's standing orders, one door each: the name, the next
  // delivery, and whether it needs a look this week.
  import { LinkCard } from "@arlen/ui-kit/components/ui/link-card";
  import { api } from "$lib/api/client";
  import { setChrome } from "$lib/chrome.svelte";
  import { nextOn } from "$lib/format";
  import { live } from "$lib/live.svelte";
  import Frame from "$lib/components/Frame.svelte";

  setChrome("Steady orders");
  const list = live(() => api.steadyList());
  const state = (s: { flagCount: number; renewedAt?: string }) =>
    s.flagCount ? `${s.flagCount} need a look` : s.renewedAt ? "renewed" : "not renewed yet";
</script>

<Frame title="Steady orders" top>
  {#if list.data}
    <div class="cards">
      {#each list.data as s (s.id)}
        <div id="steady-{s.id}" data-testid="steady-{s.id}">
          <LinkCard href="/steady/{s.id}" title={s.name} description="Next {nextOn(s.weekday)}, {state(s)}" />
        </div>
      {:else}
        <p class="t-quiet">No steady orders yet.</p>
      {/each}
    </div>
  {:else if list.error}
    <p class="t-quiet">Cannot read the steady orders: {list.error}</p>
  {/if}
</Frame>

<style>
  .cards {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
</style>
