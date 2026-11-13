<script lang="ts">
  import { page } from "$app/state";
  import { Page } from "@arlen/ui-kit/components/ui/page";
  import { SectionGrid } from "@arlen/ui-kit/components/ui/section-grid";
  import { Section } from "@arlen/ui-kit/components/ui/section";
  import { Row } from "@arlen/ui-kit/components/ui/row";
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import { Notice } from "@arlen/ui-kit/components/ui/notice";
  import { api } from "$lib/api/client";
  import type { SteadyOrder } from "$lib/api/types";
  import SteadyLineRow from "$lib/components/SteadyLineRow.svelte";
  import { dayTime } from "$lib/format";

  const sid = $derived(page.params.id ?? "");
  let order = $state<SteadyOrder | null>(null);
  let error = $state("");
  let busy = $state(false);

  $effect(() => {
    api
      .steadyOrder(sid)
      .then((o) => (order = o))
      .catch((e) => (error = `This Steady Order could not be loaded: ${(e as Error).message}`));
  });

  async function act(fn: () => Promise<SteadyOrder>) {
    busy = true;
    try {
      order = await fn();
      error = "";
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = false;
    }
  }

  const waiting = $derived(order?.lines.filter((l) => l.result === "waiting" || l.result === "flagged").length ?? 0);
  const alone = $derived(order?.lines.filter((l) => l.result === "renewed" || l.result === "split_renewed").length ?? 0);
</script>

<Page
  title={order?.name ?? "Steady Order"}
  description={order ? `Every ${order.weekday}, learned from ${order.weeksLearned} weeks with ${order.guestsPerWeek} guests a week.` : undefined}
  back={{ href: "/steady", label: "Steady Orders" }}
>
  <SectionGrid>
    {#if error}<Notice tone="error" text={error} />{/if}
    {#if order}
      {#if order.simulatedHistory}
        <Notice tone="caution" id="simulated-history" text="Simulated history. The 8 weeks behind this order are invented for the demo; prices and stock come from Valio." />
      {/if}
      <Section id="renewal">
        <Row
          label={order.renewedAt ? `Renewed ${dayTime(order.renewedAt)}` : "Not renewed this week yet"}
          description={order.renewedAt
            ? `${alone} ${alone === 1 ? "line" : "lines"} renewed alone, ${waiting} ${waiting === 1 ? "waits" : "wait"} for you.`
            : "Renewal runs every line through the same rules as a new request."}
        >
          {#snippet control()}
            {#if !order!.renewedAt}
              <Button id="renew" size="sm" disabled={busy} onclick={() => act(() => api.renew(order!.id))}>Renew now</Button>
            {/if}
          {/snippet}
        </Row>
      </Section>
      <Section label="Lines" id="lines">
        {#each order.lines as line (line.productId)}
          <SteadyLineRow {line} {busy} onaccept={() => act(() => api.acceptLine(order!.id, line.productId))} />
        {/each}
      </Section>
    {/if}
  </SectionGrid>
</Page>
