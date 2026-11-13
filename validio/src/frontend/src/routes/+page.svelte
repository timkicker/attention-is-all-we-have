<script lang="ts">
  import { Page } from "@arlen/ui-kit/components/ui/page";
  import { Section } from "@arlen/ui-kit/components/ui/section";
  import { Row } from "@arlen/ui-kit/components/ui/row";
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import { Notice } from "@arlen/ui-kit/components/ui/notice";
  import { SegmentedControl } from "@arlen/ui-kit/components/ui/segmented-control";
  import { api, LIVE } from "$lib/api/client";
  import type { DemoState, InboxItem, RequestStatus, SpendPass } from "$lib/api/types";
  import Columns from "$lib/components/Columns.svelte";
  import InboxRow from "$lib/components/InboxRow.svelte";
  import SpendPassCard from "$lib/components/SpendPassCard.svelte";
  import { poll } from "$lib/poll";

  let items = $state<InboxItem[]>([]);
  let pass = $state<SpendPass | null>(null);
  let demo = $state<DemoState | null>(null);
  let error = $state("");
  let loaded = $state(false);
  let filter = $state("all");

  const GROUPS: Record<string, RequestStatus[]> = {
    alone: ["ordered_alone"],
    waiting: ["waiting"],
    blocked: ["blocked", "rejected"],
  };
  const count = (k: string) => items.filter((i) => GROUPS[k].includes(i.status)).length;
  // A phone has room for one word per segment.
  let narrow = $state(false);
  $effect(() => {
    const mq = matchMedia("(max-width: 640px)");
    narrow = mq.matches;
    const on = () => (narrow = mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  });
  const options = $derived([
    { value: "all", label: `All ${items.length}` },
    { value: "alone", label: `${narrow ? "Alone" : "Ordered alone"} ${count("alone")}` },
    { value: "waiting", label: `${narrow ? "Waiting" : "Waiting for you"} ${count("waiting")}` },
    { value: "blocked", label: `Blocked ${count("blocked")}` },
  ]);
  const shown = $derived(filter === "all" ? items : items.filter((i) => GROUPS[filter].includes(i.status)));

  $effect(() =>
    poll(async () => {
      try {
        [items, demo] = await Promise.all([api.inbox(), api.demoState()]);
        pass ??= await api.spendPass("M-1");
        error = "";
      } catch (e) {
        error = `The inbox could not be loaded: ${(e as Error).message}`;
      } finally {
        loaded = true;
      }
    }),
  );

  async function stockOut() {
    demo = await api.stockOut();
    items = await api.inbox();
  }
  async function reset() {
    await api.reset();
    [items, demo] = await Promise.all([api.inbox(), api.demoState()]);
  }
</script>

<div class="wide">
  <Page title="Inbox" description="Every request the kitchen's agent sent and what Validio did with it.">
    <Columns>
      {#snippet main()}
        {#if error}<Notice tone="error" text={error} />{/if}
        <SegmentedControl id="inbox-filter" ariaLabel="Show requests" {options} bind:value={filter} />
        {#if loaded && shown.length === 0}
          <Section>
            <Row label={filter === "all" ? "No requests yet" : "Nothing in this group"} description="Requests appear here as soon as the agent calls request_supply." />
          </Section>
        {:else}
          <Section label="Requests" id="inbox">
            {#each shown as item (item.id)}
              <InboxRow {item} />
            {/each}
          </Section>
        {/if}
      {/snippet}
      {#snippet aside()}
        {#if pass}<SpendPassCard {pass} />{/if}
        <Section label="Demo controls">
          <Row label="Stock-out of 466375" description="Simulated. Valio really has 11,603 bags of this mozzarella; the button sets it to zero for the demo.">
            {#snippet control()}
              <Button id="stock-out" size="sm" variant="outline" disabled={demo?.stockOut466375} onclick={stockOut}>
                {demo?.stockOut466375 ? "Simulated" : "Simulate"}
              </Button>
            {/snippet}
          </Row>
          {#if !LIVE}
            <Row label="Start over" description="Back to the state the demo starts from.">
              {#snippet control()}
                <Button id="reset" size="sm" variant="ghost" onclick={reset}>Reset</Button>
              {/snippet}
            </Row>
          {/if}
        </Section>
      {/snippet}
    </Columns>
  </Page>
</div>

<style>
  .wide {
    --width-section-body: 72rem;
  }
</style>
