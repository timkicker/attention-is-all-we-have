<script lang="ts">
  // The owner's one decision, made on the phone: one question, the proposal,
  // why not the others folded, two buttons of the same weight. The approval
  // code is asked when a button is pressed, once per visit.
  import { page } from "$app/state";
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import * as Collapsible from "@arlen/ui-kit/components/ui/collapsible";
  import { Check, Circle } from "@lucide/svelte";
  import { ApiError, api } from "$lib/api/client";
  import type { Order, RankedOption } from "$lib/api/types";
  import { bump, setChrome } from "$lib/chrome.svelte";
  import { VERDICT, amount, day, look, money, nameWord, sentences, time } from "$lib/format";
  import { live } from "$lib/live.svelte";
  import CodeField from "$lib/components/CodeField.svelte";
  import State from "$lib/components/State.svelte";
  import { isCode, owner } from "$lib/owner.svelte";

  const id = $derived(page.params.id ?? "");
  // The phone link names the request (/approve/R-2); an order id works too.
  const order = live(async () => {
    const key = id;
    if (!key.startsWith("R-")) return api.order(key);
    const r = await api.request(key);
    if (!r.orderId) throw new Error("this request has no order to approve");
    return api.order(r.orderId);
  });
  const req = live(() => (order.data?.requestId ? api.request(order.data.requestId) : Promise.resolve(undefined)));

  $effect(() => {
    const rid = order.data?.requestId;
    setChrome("Approve", rid ? { href: `/requests/${rid}`, label: `the request` } : { href: "/", label: "Inbox" });
  });

  // The press that waits for the code, if the owner has not typed it yet.
  let pending = $state<null | "approve" | "reject">(null);
  let busy = $state(false);
  let problem = $state("");
  let done = $state<Order | undefined>();

  const shown = $derived(done ?? order.data);
  const chosen = $derived(new Set((shown?.lines ?? []).map((l) => l.productId)));
  // Every option of the request that was not proposed, for "why not the others".
  const passed = $derived(
    (req.data?.lines ?? [])
      .flatMap((l) => [...l.options, ...(l.substitutes ?? []), ...(l.beyondList ?? [])])
      .filter((o: RankedOption) => !chosen.has(o.productId)),
  );

  function question(o: Order): string {
    if (o.lines.length === 1) {
      const l = o.lines[0];
      return `Order ${amount(l.quantity, l.unit)} of ${nameWord(l.name)} for ${money(o.totalCents)}?`;
    }
    return `Order these ${o.lines.length} lines for ${money(o.totalCents)}?`;
  }

  function press(kind: "approve" | "reject") {
    problem = "";
    if (!isCode(owner.code)) {
      pending = kind;
      return;
    }
    void decide(kind);
  }

  async function decide(kind: "approve" | "reject") {
    if (!shown || busy) return;
    busy = true;
    try {
      done = await (kind === "approve" ? api.approve(shown.id) : api.reject(shown.id));
      pending = null;
      bump();
    } catch (e) {
      const status = e instanceof ApiError ? e.status : 0;
      if (status === 403) {
        owner.code = "";
        pending = kind;
      }
      problem =
        status === 403
          ? "That code is not right."
          : status === 429
            ? "Too many wrong codes for this order."
            : e instanceof Error
              ? e.message
              : String(e);
    } finally {
      busy = false;
    }
  }

  const STEP: Record<string, string> = {
    waiting: "Asked you",
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
      <h2 id="question" data-testid="approve-question">{question(shown)}</h2>
      <ul class="lines">
        {#each shown.lines as l (l.productId)}
          <li class="card">
            <span class="top"><span class="name">{nameWord(l.name)}</span><span class="num price">{money(l.totalCents)}</span></span>
            <span class="t-quiet meta">
              <span class="mono">{l.productId}</span>{#if l.deliveryDate}<span>delivery {day(l.deliveryDate)}</span>{/if}{#if l.isSubstitute && !l.onValioList}<span>not on Valio's list</span>{/if}
            </span>
          </li>
        {/each}
      </ul>
      {#if req.data?.question}
        <p class="reason">{sentences(req.data.question)[0]}</p>
      {/if}
      {#if passed.length}
        <Collapsible.Root>
          <Collapsible.Trigger class="fold" id="fold-others">
            <Collapsible.Chevron />
            Why not the others ({passed.length})
          </Collapsible.Trigger>
          <Collapsible.Content>
            <ul class="others">
              {#each passed as o (o.productId)}
                {@const v = look(VERDICT, o.verdict)}
                <li>
                  <span class="o-name">{nameWord(o.name)}</span>
                  <State label={v.label} tone={v.tone} />
                  <span class="o-why t-quiet">{sentences(o.sentence)[0] ?? ""}</span>
                </li>
              {/each}
            </ul>
          </Collapsible.Content>
        </Collapsible.Root>
      {/if}

      {#if pending}
        <div class="code">
          <CodeField onready={() => decide(pending!)} {problem} action={pending === "approve" ? "Approve" : "Reject"} />
        </div>
      {:else if problem}
        <p class="problem t-bad" id="approve-problem" role="alert">{problem}</p>
      {/if}
      <div class="buttons">
        <Button variant="outline" size="lg" id="reject" data-testid="reject" disabled={busy} onclick={() => press("reject")}>Reject</Button>
        <Button size="lg" id="approve" data-testid="approve" disabled={busy} onclick={() => press("approve")}>Approve</Button>
      </div>
    {:else}
      <h2 id="outcome">
        {shown.state === "placed" ? "Ordered" : STEP[shown.state] ?? shown.state}
        {#if shown.lines.length === 1}{amount(shown.lines[0].quantity, shown.lines[0].unit)} of {nameWord(shown.lines[0].name)},{/if}
        <span class="num">{money(shown.totalCents)}</span>
      </h2>
      <ol class="steps" id="order-steps" data-testid="order-steps">
        {#each shown.history as h, i (i)}
          <li>
            {#if i === shown.history.length - 1}<Check size={14} strokeWidth={2} aria-hidden="true" />{:else}<Circle size={10} strokeWidth={2} aria-hidden="true" />{/if}
            <span>{STEP[h.state] ?? h.state}</span>
            <span class="t-quiet num">{time(h.at)}</span>
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
  .card {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
    padding: 0.75rem 0.9rem;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-card);
  }
  .top {
    display: flex;
    justify-content: space-between;
    gap: 0.75rem;
  }
  .name {
    font-weight: 500;
  }
  .price {
    font-weight: 500;
    white-space: nowrap;
  }
  .meta {
    display: flex;
    flex-wrap: wrap;
    gap: 0.1rem 0.75rem;
    font-size: var(--text-xs);
  }
  .reason {
    margin: 0;
    font-size: var(--text-sm);
    color: var(--color-fg-secondary);
  }
  .approve :global(.fold) {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    font-size: var(--text-sm);
    font-weight: 500;
    color: var(--color-fg-secondary);
  }
  .others {
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
    margin: 0.6rem 0 0;
    padding: 0;
    list-style: none;
    font-size: var(--text-sm);
  }
  .others li {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 0.15rem 0.75rem;
    align-items: center;
  }
  .o-why {
    grid-column: 1 / -1;
    font-size: var(--text-xs);
  }
  .code {
    margin-top: 0.25rem;
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
      padding: 1.5rem 1rem calc(6rem + env(safe-area-inset-bottom));
    }
    /* The two answers stay under the thumb. */
    .buttons {
      position: fixed;
      inset-inline: 0;
      bottom: 0;
      z-index: 10;
      margin: 0;
      padding: 0.75rem 1rem calc(0.75rem + env(safe-area-inset-bottom));
      border-top: 1px solid var(--color-border);
      background: var(--color-bg-app);
    }
    .buttons :global(button) {
      min-height: 44px;
    }
  }
</style>
