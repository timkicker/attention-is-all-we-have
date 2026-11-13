<script lang="ts">
  // The owner's one decision, made on the phone: one question, the code, two
  // buttons of the same weight. Nothing else on the page.
  import { page } from "$app/state";
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import { Check } from "@lucide/svelte";
  import { ApiError, api } from "$lib/api/client";
  import type { Order } from "$lib/api/types";
  import { bump, setChrome } from "$lib/chrome.svelte";
  import { amount, day, money, time } from "$lib/format";
  import { live } from "$lib/live.svelte";
  import CodeField from "$lib/components/CodeField.svelte";
  import Info from "$lib/components/Info.svelte";
  import { isCode, owner } from "$lib/owner.svelte";

  const id = $derived(page.params.id ?? "");
  const order = live(() => api.order(id));
  const req = live(() => (order.data?.requestId ? api.request(order.data.requestId) : Promise.resolve(undefined)));

  $effect(() => {
    const rid = order.data?.requestId;
    setChrome("Approve", rid ? { href: `/requests/${rid}`, label: `Request ${rid}` } : { href: "/", label: "Inbox" });
  });

  // Ask for the code unless the owner typed it earlier in this session.
  let ask = $state(!isCode(owner.code));
  let typed = $state("");
  let busy = $state(false);
  let problem = $state("");
  let done = $state<Order | undefined>();

  const shown = $derived(done ?? order.data);

  function question(o: Order): string {
    if (o.lines.length === 1) {
      const l = o.lines[0];
      return `Approve ${amount(l.quantity, l.unit)} of ${l.productId} for ${money(o.totalCents)}?`;
    }
    return `Approve order ${o.id} for ${money(o.totalCents)}?`;
  }

  async function decide(kind: "approve" | "reject") {
    if (!shown || busy) return;
    problem = "";
    if (ask) {
      if (!isCode(typed)) {
        problem = "Enter the 6 digit approval code first.";
        return;
      }
      owner.code = typed;
    }
    busy = true;
    try {
      done = await (kind === "approve" ? api.approve(shown.id) : api.reject(shown.id));
      bump();
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) {
        owner.code = "";
        ask = true;
      }
      problem =
        e instanceof ApiError && e.status === 403
          ? "That code is not right."
          : e instanceof ApiError && e.status === 429
            ? "Too many wrong codes for this order."
            : e instanceof Error
              ? e.message
              : String(e);
    } finally {
      busy = false;
    }
  }

  const STEP: Record<string, string> = {
    waiting: "Waiting for you",
    approved: "Approved",
    placed: "Placed at Valio",
    rejected: "Rejected",
    blocked: "Blocked by the rules",
  };
</script>

<div class="approve">
  {#if order.error && !shown}
    <p class="t-quiet">Order {id}: {order.error}</p>
  {:else if shown}
    {#if shown.state === "waiting"}
      <h2 id="question">{question(shown)}</h2>
      <ul class="lines">
        {#each shown.lines as l (l.productId)}
          <li>
            <span class="name">{l.name}</span>
            <span class="t-quiet">
              {#if l.deliveryDate}Delivered {day(l.deliveryDate)}{/if}{#if l.isSubstitute && !l.onValioList}, not on Valio's list{/if}
            </span>
          </li>
        {/each}
      </ul>
      {#if req.data?.question}
        <p class="why">
          <span class="t-quiet">Why you are asked</span>
          <Info label="Why you are asked" text={req.data.question} id="why-asked" />
        </p>
      {/if}
      <form class="form" onsubmit={(e) => { e.preventDefault(); decide("approve"); }}>
        {#if ask}
          <CodeField {problem} bind:value={typed} />
        {:else if problem}
          <p class="problem t-bad" id="approve-problem" role="alert">{problem}</p>
        {/if}
        <div class="buttons">
          <Button variant="outline" size="lg" id="reject" disabled={busy} onclick={() => decide("reject")}>Reject</Button>
          <Button size="lg" type="submit" id="approve" disabled={busy}>Approve</Button>
        </div>
      </form>
    {:else}
      <h2 id="outcome">
        {shown.state === "placed" ? "Ordered" : shown.state === "rejected" ? "Rejected" : STEP[shown.state] ?? shown.state}
        <span class="t-quiet num">{money(shown.totalCents)}</span>
      </h2>
      <ol class="steps" id="order-steps">
        {#each shown.history as h, i (i)}
          <li>
            <Check size={14} strokeWidth={2} aria-hidden="true" />
            <span>{STEP[h.state] ?? h.state}</span>
            <span class="t-quiet num">{time(h.at).slice(0, 5)}</span>
          </li>
        {/each}
      </ol>
      <Button variant="outline" href={shown.requestId ? `/requests/${shown.requestId}` : "/"}>Back to the request</Button>
    {/if}
  {/if}
</div>

<style>
  .approve {
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
    max-width: 26rem;
    margin: 0 auto;
    padding: 3rem 1.25rem;
  }
  h2 {
    margin: 0;
    font-size: var(--text-xl);
    font-weight: 600;
    line-height: 1.3;
  }
  .lines {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    margin: 0;
    padding: 0;
    list-style: none;
    font-size: var(--text-sm);
  }
  .lines li {
    display: flex;
    flex-direction: column;
  }
  .name {
    font-weight: 500;
  }
  .why {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    margin: 0;
    font-size: var(--text-sm);
  }
  .form {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    margin-top: 0.5rem;
  }
  .problem {
    margin: 0;
    font-size: var(--text-sm);
  }
  .buttons {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.75rem;
    margin-top: 0.75rem;
  }
  .steps {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    margin: 0;
    padding: 0;
    list-style: none;
    font-size: var(--text-sm);
  }
  .steps li {
    display: grid;
    grid-template-columns: auto 1fr auto;
    align-items: center;
    gap: 0.5rem;
  }
  @media (max-width: 760px) {
    .approve {
      padding: 1.5rem 1rem calc(1.5rem + env(safe-area-inset-bottom));
      min-height: calc(100svh - 3rem);
    }
    .buttons {
      margin-top: auto;
    }
  }
</style>
