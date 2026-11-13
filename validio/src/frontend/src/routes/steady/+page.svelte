<script lang="ts">
  import { Page } from "@arlen/ui-kit/components/ui/page";
  import { SectionGrid } from "@arlen/ui-kit/components/ui/section-grid";
  import { LinkCard } from "@arlen/ui-kit/components/ui/link-card";
  import { Notice } from "@arlen/ui-kit/components/ui/notice";
  import { api } from "$lib/api/client";
  import type { SteadyOrderSummary } from "$lib/api/types";
  import { dayTime } from "$lib/format";

  let list = $state<SteadyOrderSummary[]>([]);
  let error = $state("");

  $effect(() => {
    api
      .steadyList()
      .then((l) => (list = l))
      .catch((e) => (error = `Steady Orders could not be loaded: ${(e as Error).message}`));
  });

  const describe = (s: SteadyOrderSummary) =>
    [
      `${s.lineCount} lines, every ${s.weekday}`,
      s.renewedAt ? `renewed ${dayTime(s.renewedAt)}` : "not renewed this week yet",
      s.flagCount ? `${s.flagCount} ${s.flagCount === 1 ? "line waits" : "lines wait"} for you` : "",
    ]
      .filter(Boolean)
      .join(", ") + ".";
</script>

<Page title="Steady Orders" description="The usual orders that renew themselves. Drift Watch holds a line when something looks off.">
  <SectionGrid>
    {#if error}<Notice tone="error" text={error} />{/if}
    {#each list as s (s.id)}
      <LinkCard href="/steady/{s.id}" title={s.name} description={describe(s)} />
    {/each}
  </SectionGrid>
</Page>
