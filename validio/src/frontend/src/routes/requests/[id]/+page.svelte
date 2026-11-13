<script lang="ts">
  import { page } from "$app/state";
  import { Page } from "@arlen/ui-kit/components/ui/page";
  import { Section } from "@arlen/ui-kit/components/ui/section";
  import { Row } from "@arlen/ui-kit/components/ui/row";
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import { Notice } from "@arlen/ui-kit/components/ui/notice";
  import { api } from "$lib/api/client";
  import type { Order, SpendPass, SupplyRequest } from "$lib/api/types";
  import Columns from "$lib/components/Columns.svelte";
  import DecisionCard from "$lib/components/DecisionCard.svelte";
  import OptionRow from "$lib/components/OptionRow.svelte";
  import SpendPassCard from "$lib/components/SpendPassCard.svelte";
  import { day, time } from "$lib/format";
  import { poll } from "$lib/poll";

  const rid = $derived(page.params.id ?? "");
  let req = $state<SupplyRequest | null>(null);
  let order = $state<Order | null>(null);
  let pass = $state<SpendPass | null>(null);
  let error = $state("");

  const ORDER_STATE = { waiting: "Waiting", approved: "Approved", placed: "Placed at Valio", rejected: "Rejected" };

  $effect(() => {
    const id = rid;
    return poll(async () => {
      try {
        req = await api.request(id);
        order = req.orderId ? await api.order(req.orderId) : null;
        pass ??= await api.spendPass(req.spendPassId);
        error = "";
      } catch (e) {
        error = `This request could not be loaded: ${(e as Error).message}`;
      }
    });
  });
</script>

<div class="wide">
  <Page
    title={req?.text ?? "Request"}
    description={req ? `Asked by ${req.agent} at ${time(req.createdAt)}. Deliver by ${day(req.deliverBy)}.` : undefined}
    back={{ href: "/", label: "Inbox" }}
  >
    {#if error}<Notice tone="error" text={error} />{/if}
    {#if req}
      <Columns>
        {#snippet main()}
          <DecisionCard request={req!}>
            {#snippet action()}
              {#if req!.status === "waiting"}
                <Button id="open-approve" href="/approve/{req!.id}">Answer on the phone page</Button>
              {/if}
            {/snippet}
          </DecisionCard>
          {#each req!.simulated ?? [] as mark (mark.what)}
            <Notice tone="caution" text={mark.sentence} id="simulated-{mark.what}" />
          {/each}

          {#each req!.lines as line (line.lineId)}
            <Section label={line.substitutes ? "Ordered product" : "Ranked options"} id="options-{line.lineId}">
              {#each line.options as option (option.productId)}
                <OptionRow {option} open={option.verdict === "chosen"} />
              {/each}
            </Section>
            {#if line.substitutes}
              <Section label="Valio's substitute list" id="substitutes-{line.lineId}">
                {#each line.substitutes as option (option.productId)}
                  <OptionRow {option} />
                {/each}
              </Section>
            {/if}
            {#if line.beyondList}
              <Section label="Found beyond the list" id="beyond-{line.lineId}">
                {#each line.beyondList as option (option.productId)}
                  <OptionRow {option} open={option.verdict === "chosen"} />
                {/each}
              </Section>
            {/if}
            {#if line.note}<p class="note">{line.note}</p>{/if}
          {/each}
        {/snippet}
        {#snippet aside()}
          {#each req!.lines as line (line.lineId)}
            <Section label="What Validio read">
              <Row label="Product">{#snippet control()}<span class="v">{line.need.what}</span>{/snippet}</Row>
              <Row label="Amount">{#snippet control()}<span class="v num">{line.need.quantity} {line.need.unit}</span>{/snippet}</Row>
              <Row label="Diet">{#snippet control()}<span class="v">{line.need.diet.join(", ")}</span>{/snippet}</Row>
              <Row label="Deliver by">{#snippet control()}<span class="v">{day(line.need.deliverBy)}</span>{/snippet}</Row>
            </Section>
          {/each}
          {#if order}
            <Section label="Order {order.id}" id="order">
              {#each order.history as step (step.state)}
                <Row label={ORDER_STATE[step.state]}>
                  {#snippet control()}<span class="v num">{time(step.at)}</span>{/snippet}
                </Row>
              {/each}
            </Section>
          {/if}
          {#if pass}<SpendPassCard {pass} />{/if}
        {/snippet}
      </Columns>
    {/if}
  </Page>
</div>

<style>
  .wide {
    --width-section-body: 72rem;
  }
  .note {
    margin: -0.75rem 0 0;
    padding-inline: 0.25rem;
    font-size: var(--text-xs);
    line-height: 1.45;
    color: color-mix(in srgb, var(--foreground) 64%, transparent);
  }
  .v {
    font-size: var(--text-sm);
    font-weight: 600;
    white-space: nowrap;
  }
</style>
