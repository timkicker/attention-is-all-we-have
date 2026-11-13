<script lang="ts">
  // The kitchen's standing orders as settings rows: what it is, when it runs,
  // what needs a look, and the way in.
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import { Page } from "@arlen/ui-kit/components/ui/page";
  import { Row } from "@arlen/ui-kit/components/ui/row";
  import { Section } from "@arlen/ui-kit/components/ui/section";
  import { SectionGrid } from "@arlen/ui-kit/components/ui/section-grid";
  import { api } from "$lib/api/client";
  import { setChrome } from "$lib/chrome.svelte";
  import { dayTime } from "$lib/format";
  import { live } from "$lib/live.svelte";

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
</script>

<Page title="Steady orders" description="Orders Validio renews every week from what the kitchen used.">
  <SectionGrid>
  {#if list.data}
    <Section>
      {#each list.data as s (s.id)}
        <Row label={s.name} description={describe(s)} id="steady-{s.id}">
          {#snippet control()}
            <Button variant="outline" size="sm" href="/steady/{s.id}" aria-label="Open {s.name}">Open</Button>
          {/snippet}
        </Row>
      {:else}
        <Row label="No steady orders yet" />
      {/each}
    </Section>
  {:else if list.error}
    <p class="t-quiet">Cannot read the steady orders: {list.error}</p>
  {/if}
  </SectionGrid>
</Page>
