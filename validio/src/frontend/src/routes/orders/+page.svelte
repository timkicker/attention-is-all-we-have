<script lang="ts">
  /// Orders: the agent's requests and the steady orders in one card of status
  /// rows, filtered by chips. Each row opens its detail page.
  import { page } from "$app/state";
  import { replaceState } from "$app/navigation";
  import { Chip } from "@arlen/ui-kit/components/ui/chip";
  import { Section } from "@arlen/ui-kit/components/ui/section";
  import { api } from "$lib/api/client";
  import type { SteadyOrder } from "$lib/api/types";
  import { dayTime, money, nextOn } from "$lib/format";
  import { live } from "$lib/live.svelte";
  import { requestPill, steadyLook, type Pill } from "$lib/v";
  import VHead from "$lib/v/VHead.svelte";
  import VState from "$lib/v/VState.svelte";
  import VStatusRow from "$lib/v/VStatusRow.svelte";

  type Filter = "all" | "waiting" | "ordered" | "blocked" | "steady";
  const FILTERS: { id: Filter; label: string }[] = [
    { id: "all", label: "All" },
    { id: "waiting", label: "Waiting" },
    { id: "ordered", label: "Ordered" },
    { id: "blocked", label: "Blocked" },
    { id: "steady", label: "Steady" },
  ];
  const ORDERED = new Set(["ordered_alone", "approved", "ordered"]);

  interface Row {
    key: string;
    href: string;
    pill: Pill;
    title: string;
    when: string;
    amount: string;
    in: Set<Filter>;
  }

  const inbox = live(() => api.inbox());
  const steadyList = live(() => api.steadyList());
  // The steady pill needs the lines' state, which only the order itself carries.
  const steady = live(async () => {
    const out: Record<string, SteadyOrder> = {};
    for (const s of await api.steadyList()) out[s.id] = await api.steadyOrder(s.id);
    return out;
  });

  const fromUrl = page.url.searchParams.get("f") as Filter | null;
  let filter = $state<Filter>(FILTERS.some((f) => f.id === fromUrl) ? (fromUrl as Filter) : "all");

  function pick(f: Filter) {
    filter = f;
    const url = new URL(page.url);
    if (f === "all") url.searchParams.delete("f");
    else url.searchParams.set("f", f);
    replaceState(url, {});
  }

  const rows = $derived.by((): Row[] => {
    const out: Row[] = [];
    for (const i of inbox.data ?? []) {
      const tags = new Set<Filter>(["all"]);
      if (i.status === "waiting") tags.add("waiting");
      if (ORDERED.has(i.status)) tags.add("ordered");
      if (i.status === "blocked") tags.add("blocked");
      out.push({
        key: `r-${i.id}`,
        href: `/requests/${i.id}`,
        pill: requestPill(i.status),
        title: i.titleText ?? i.displayName ?? i.title ?? i.text,
        when: dayTime(i.createdAt),
        amount: i.moneyText ?? money(i.totalCents),
        in: tags,
      });
    }
    for (const s of steadyList.data ?? []) {
      const o = steady.data?.[s.id];
      const look = steadyLook(o, s.state);
      const tags = new Set<Filter>(["all", "steady"]);
      if (look.pill.tone === "wait") tags.add("waiting");
      if (look.pill.tone === "ok") tags.add("ordered");
      // What was placed this week, as the order's own page says it.
      const cents = o?.state === "renewed" ? o.steadyPass?.usedCents : undefined;
      out.push({
        key: `s-${s.id}`,
        href: `/steady/${s.id}`,
        pill: look.pill,
        title: s.name,
        when: `Next ${nextOn(s.weekday)}`,
        amount: cents ? money(cents) : `${s.lineCount} lines`,
        in: tags,
      });
    }
    return out;
  });

  const shown = $derived(rows.filter((r) => r.in.has(filter)));
  const loaded = $derived(inbox.loaded && steadyList.loaded);
  const error = $derived((inbox.error && !inbox.data) || (steadyList.error && !steadyList.data) ? (inbox.error ?? steadyList.error) : "");
</script>

<VHead title="Orders" />

<div class="blocks">
  {#if error}
    <VState kind="error" title="Validio is not reachable." detail={error} onretry={() => location.reload()} />
  {:else if !loaded}
    <VState kind="loading" />
  {:else if !rows.length}
    <VState kind="empty" title="No orders yet." />
  {:else}
    <section class="sec" aria-label="Orders">
    <div class="chips" role="group" aria-label="Show">
      {#each FILTERS as f (f.id)}
        <Chip id="filter-{f.id}" label={f.label} pressed={filter === f.id} onclick={() => pick(f.id)} />
      {/each}
    </div>
    {#if shown.length}
      <Section class="v-card">
        {#each shown as r (r.key)}
          <VStatusRow href={r.href} testid="order-{r.key}" id="order-{r.key}" pill={r.pill} title={r.title} sub={r.when} end={r.amount} />
        {/each}
      </Section>
    {:else}
      <VState kind="empty" title="None." />
    {/if}
    </section>
  {/if}
</div>

<style>
  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 12px;
  }
  .chips :global(.chip) {
    height: 28px;
  }
  /* On the phone each chip is a whole finger's hit. */
  @media (max-width: 760px) {
    .chips {
      gap: 6px;
    }
    .chips :global(.chip) {
      height: 44px;
      padding: 0;
    }
    .chips :global(.chip-body) {
      justify-content: center;
      min-width: 44px;
      height: 44px;
      padding: 0 10px;
    }
  }
</style>
