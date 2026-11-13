<script lang="ts">
  // The kitchen's standing orders, each a door to its page: what it is, when
  // it runs, what needs a look.
  import { CalendarSync } from "@lucide/svelte";
  import { LinkCard } from "@arlen/ui-kit/components/ui/link-card";
  import { Page } from "@arlen/ui-kit/components/ui/page";
  import { SectionGrid } from "@arlen/ui-kit/components/ui/section-grid";
  import { api } from "$lib/api/client";
  import { setChrome } from "$lib/chrome.svelte";
  import { dayTime } from "$lib/format";
  import { live } from "$lib/live.svelte";
  import Facts from "$lib/components/Facts.svelte";
  import Info from "$lib/components/Info.svelte";

  setChrome("Steady orders");
  const list = live(() => api.steadyList());

  const describe = (s: { weekday: string; lineCount: number; flagCount: number; renewedAt?: string }) =>
    [
      `Every ${s.weekday}`,
      `${s.lineCount} lines`,
      s.flagCount ? `${s.flagCount} need a look` : "",
      s.renewedAt ? `renewed ${dayTime(s.renewedAt)}` : "not renewed this week",
    ]
      .filter(Boolean)
      .join(", ");
  const lines = $derived((list.data ?? []).reduce((n, s) => n + s.lineCount, 0));
</script>

<Page title="Steady orders">
  <SectionGrid>
    {#if list.data}
      <div class="figures">
        <Facts
          items={[
            { value: String(list.data.length), label: list.data.length === 1 ? "steady order" : "steady orders" },
            { value: String(lines), label: "lines" },
          ]}
        />
        <Info label="What a steady order is" text="An order Validio renews every week from what the kitchen used, and asks the chef about when a line drifts." />
      </div>
      {#each list.data as s (s.id)}
        <div class="door" data-testid="steady-{s.id}" id="steady-{s.id}">
          <LinkCard href="/steady/{s.id}" title={s.name} description={describe(s)}>
            {#snippet icon()}<CalendarSync size={20} strokeWidth={1.75} />{/snippet}
          </LinkCard>
        </div>
      {:else}
        <p class="t-quiet">No steady orders yet.</p>
      {/each}
    {:else if list.error}
      <p class="t-quiet">Cannot read the steady orders: {list.error}</p>
    {/if}
  </SectionGrid>
</Page>

<style>
  .figures {
    display: flex;
    align-items: center;
    gap: 0.35rem;
  }
  .door {
    display: contents;
  }
</style>
