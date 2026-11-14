<script lang="ts">
  /// Steady orders: one "This week" card, one status row per order.
  import { Section } from "@arlen/ui-kit/components/ui/section";
  import { api } from "$lib/api/client";
  import type { SteadyOrder } from "$lib/api/types";
  import { nextOn } from "$lib/format";
  import { live } from "$lib/live.svelte";
  import { steadyLook } from "$lib/v";
  import VHead from "$lib/v/VHead.svelte";
  import VState from "$lib/v/VState.svelte";
  import VStatusRow from "$lib/v/VStatusRow.svelte";

  const list = live(() => api.steadyList());
  // The pill needs the lines' state, which only the order itself carries.
  const orders = live(async () => {
    const out: Record<string, SteadyOrder> = {};
    for (const s of await api.steadyList()) out[s.id] = await api.steadyOrder(s.id);
    return out;
  });
</script>

<VHead title="Steady orders" />

<div class="blocks">
  {#if list.error && !list.data}
    <VState kind="error" title="Validio is not reachable." detail={list.error} onretry={() => location.reload()} />
  {:else if !list.loaded}
    <VState kind="loading" rows={1} />
  {:else if !list.data?.length}
    <VState kind="empty" title="No Steady Orders yet." />
  {:else}
    <section class="sec" aria-labelledby="h-week">
      <h2 class="v-h" id="h-week">This week</h2>
      <Section class="v-card">
        {#each list.data as s (s.id)}
          {@const o = orders.data?.[s.id]}
          {@const look = steadyLook(o, s.state)}
          <VStatusRow
            href="/steady/{s.id}"
            testid="steady-{s.id}"
            id="steady-{s.id}"
            pill={look.pill}
            title={s.name}
            sub="Next delivery {nextOn(s.weekday)}{o ? `\u2003${o.guestsPerWeek} guests a week` : ''}"
            end={look.right}
          />
        {/each}
      </Section>
    </section>
  {/if}
</div>
