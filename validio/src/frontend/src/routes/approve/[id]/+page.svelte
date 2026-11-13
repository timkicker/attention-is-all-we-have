<script lang="ts">
  // One-Tap Approve: the owner's phone page. One sentence, the option it is
  // about and two buttons. Built for a 390 px screen.
  import { page } from "$app/state";
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import { Notice } from "@arlen/ui-kit/components/ui/notice";
  import { Badge } from "@arlen/ui-kit/components/ui/badge";
  import { api } from "$lib/api/client";
  import type { Order, RankedOption, SupplyRequest } from "$lib/api/types";
  import StatusBadge from "$lib/components/StatusBadge.svelte";
  import { money, time } from "$lib/format";

  const rid = $derived(page.params.id ?? "");
  let req = $state<SupplyRequest | null>(null);
  let order = $state<Order | null>(null);
  let error = $state("");
  let busy = $state(false);

  const ORDER_STATE = { waiting: "Waiting", approved: "Approved", placed: "Placed at Valio", rejected: "Rejected" };

  async function load(id: string) {
    try {
      req = await api.request(id);
      order = req.orderId ? await api.order(req.orderId) : null;
      error = "";
    } catch (e) {
      error = `This question could not be loaded: ${(e as Error).message}`;
    }
  }
  $effect(() => {
    load(rid);
  });

  const line = $derived(req?.lines[0]);
  const pick = $derived<RankedOption | undefined>(
    line?.beyondList?.find((o) => o.verdict === "chosen") ?? line?.options.find((o) => o.verdict === "chosen"),
  );
  const refused = $derived((line?.substitutes ?? []).filter((o) => o.verdict !== "chosen"));

  async function answer(kind: "approve" | "reject") {
    if (!req?.orderId || busy) return;
    busy = true;
    try {
      order = kind === "approve" ? await api.approve(req.orderId) : await api.reject(req.orderId);
      req = await api.request(req.id);
      error = "";
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = false;
    }
  }
</script>

<div class="phone" id="approve-page">
  {#if error}<Notice tone="error" text={error} />{/if}
  {#if req}
    <div class="ask">
      <div class="who">
        <StatusBadge status={req.status} />
        <span class="num">{time(req.createdAt)}</span>
      </div>
      <p class="question" id="question">{req.question ?? req.decision.sentence}</p>
    </div>

    {#if pick}
      <div class="pick" id="pick">
        <div class="pick-head">
          <span class="pick-name">{pick.name}</span>
          <span class="pick-total num">{money(pick.totalCents)}</span>
        </div>
        <span class="pick-meta num">{pick.quantity} {pick.unit}, product {pick.productId}{pick.onValioList === false ? ", outside Valio's list" : ""}</span>
        <p class="pick-why">{pick.sentence}</p>
      </div>
    {/if}

    {#if refused.length}
      <ul class="refused" aria-label="Listed substitutes that were refused">
        {#each refused as o (o.productId)}
          <li>
            <Badge variant={o.verdict === "blocked" ? "destructive" : "warn"}>{o.verdict === "blocked" ? "Blocked" : "Not deliverable"}</Badge>
            <span>{o.name}</span>
          </li>
        {/each}
      </ul>
    {/if}

    {#each req.simulated ?? [] as mark (mark.what)}
      <Notice tone="caution" text={mark.sentence} />
    {/each}

    {#if req.status === "waiting"}
      <div class="buttons">
        <Button id="approve" size="lg" class="w-full" disabled={busy} onclick={() => answer("approve")}>Approve</Button>
        <Button id="reject" size="lg" variant="outline" class="w-full" disabled={busy} onclick={() => answer("reject")}>Reject</Button>
      </div>
      <p class="fine">Validio asks Valio again before it orders. If the price rose by more than 2 % or a line can no longer be delivered, nothing is ordered.</p>
    {:else if order}
      <ol class="steps" id="order-steps" aria-label="Order {order.id}">
        {#each order.history as step (step.state)}
          <li><span>{ORDER_STATE[step.state]}</span><span class="num">{time(step.at)}</span></li>
        {/each}
      </ol>
      <p class="fine" id="answered">{req.decision.sentence}</p>
    {/if}
  {/if}
</div>

<style>
  .phone {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    max-width: 26rem;
    margin-inline: auto;
    padding: 1.25rem 1rem 2rem;
  }
  .ask {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }
  .who {
    display: flex;
    align-items: center;
    gap: 0.625rem;
    font-size: var(--text-xs);
    color: color-mix(in srgb, var(--foreground) 64%, transparent);
  }
  .question {
    margin: 0;
    font-size: var(--text-xl);
    line-height: 1.35;
    font-weight: 600;
    color: var(--foreground);
    text-wrap: pretty;
  }
  .pick {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    padding: 0.875rem 1rem;
    border-radius: var(--radius-card);
    border: 1px solid color-mix(in srgb, var(--color-success) 45%, transparent);
    background: var(--card);
  }
  .pick-head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 1rem;
  }
  .pick-name {
    font-size: var(--text-base);
    font-weight: 600;
  }
  .pick-total {
    font-size: var(--text-lg);
    font-weight: 700;
    white-space: nowrap;
  }
  .pick-meta {
    font-size: var(--text-xs);
    color: color-mix(in srgb, var(--foreground) 64%, transparent);
  }
  .pick-why {
    margin: 0.25rem 0 0;
    font-size: var(--text-sm);
    line-height: 1.45;
  }
  .refused {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
    margin: 0;
    padding: 0 0.25rem;
    list-style: none;
    font-size: var(--text-xs);
    color: color-mix(in srgb, var(--foreground) 72%, transparent);
  }
  .refused li {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .buttons {
    display: grid;
    gap: 0.625rem;
    margin-top: 0.25rem;
  }
  .fine {
    margin: 0;
    font-size: var(--text-xs);
    line-height: 1.5;
    color: color-mix(in srgb, var(--foreground) 64%, transparent);
  }
  .steps {
    display: flex;
    flex-direction: column;
    margin: 0;
    padding: 0;
    list-style: none;
    border-radius: var(--radius-card);
    border: 1px solid color-mix(in srgb, var(--foreground) 10%, transparent);
    background: var(--card);
  }
  .steps li {
    display: flex;
    justify-content: space-between;
    padding: var(--space-row, 0.75rem) 1rem;
    font-size: var(--text-sm);
    font-weight: 500;
  }
  .steps li + li {
    border-top: 1px solid color-mix(in srgb, var(--foreground) 7%, transparent);
  }
</style>
