<script lang="ts">
  // The owner's one decision, made on the phone: one question, the proposal,
  // why not the others folded, two buttons of the same weight. The approval
  // code is asked when a button is pressed, once per visit.
  import { page } from "$app/state";
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import * as Collapsible from "@arlen/ui-kit/components/ui/collapsible";
  import { ApiError, api } from "$lib/api/client";
  import type { Order, RankedOption } from "$lib/api/types";
  import { bump, setChrome } from "$lib/chrome.svelte";
  import { VERDICT, amount, day, hm, look, money, nameWord, sentences, stockOutLine, time } from "$lib/format";
  import { live } from "$lib/live.svelte";
  import CodeField from "$lib/components/CodeField.svelte";
  import Frame from "$lib/components/Frame.svelte";
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
    const placed = !!done || (order.data && order.data.state !== "waiting");
    setChrome(placed ? "Ordered" : "Approve", rid ? { href: `/requests/${rid}`, label: "Request" } : { href: "/", label: "Inbox" });
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

  // One reason line: what speaks for the proposal, and when it comes.
  const reason = $derived.by(() => {
    const o = shown;
    if (!o || o.lines.length !== 1) return "";
    const l = o.lines[0];
    const opt = (req.data?.lines ?? []).flatMap((x) => [...x.options, ...(x.substitutes ?? []), ...(x.beyondList ?? [])]).find((x) => x.productId === l.productId);
    const why = stockOutLine(req.data) || (sentences(opt?.sentence)[0] ?? "");
    return [why, l.deliveryDate ? `Delivery ${day(l.deliveryDate)}.` : ""].filter(Boolean).join(" ");
  });

  function outcome(o: Order): string {
    const word = o.state === "placed" ? "Ordered" : (STEP[o.state] ?? o.state);
    const what = o.lines.length === 1 ? ` ${amount(o.lines[0].quantity, o.lines[0].unit)} of ${nameWord(o.lines[0].name)},` : "";
    return `${word}${what} ${money(o.totalCents)}`;
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
            ? "Too many tries. Wait a few minutes, then try again."
            : status === 409
              ? `Cannot do that now: ${e instanceof Error ? e.message : "the order changed"}.`
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

{#if order.error && !shown}
  <Frame title="Approve" narrow><p class="t-quiet">Order {id}: {order.error}</p></Frame>
{:else if shown && shown.state === "waiting"}
  <Frame title={question(shown)} titleId="question" titleTestid="approve-question" narrow>
    {#if reason}<p class="reason" id="approve-reason">{reason}</p>{/if}
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
      <CodeField onready={() => decide(pending!)} {problem} action={pending === "approve" ? "Approve" : "Reject"} />
    {:else if problem}
      <p class="problem t-bad" id="approve-problem" role="alert">{problem}</p>
    {/if}
    <div class="buttons">
      <Button variant="outline" size="lg" id="reject" data-testid="reject" disabled={busy} onclick={() => press("reject")}>Reject</Button>
      <Button size="lg" id="approve" data-testid="approve" disabled={busy} onclick={() => press("approve")}>Approve</Button>
    </div>
  </Frame>
{:else if shown}
  <Frame title={outcome(shown)} titleId="outcome" titleTestid="approve-question" narrow>
    <p class="reason">
      {shown.state === "placed" ? `Approved, order ${shown.id} placed at Valio ${hm(shown.history.at(-1)?.at ?? "")}.` : `Order ${shown.id}.`}
      <a href="/ledger">See it in the ledger</a>
    </p>
    <!-- The steps say again what the sentence says; the record keeps them. -->
    <ol hidden id="order-steps" data-testid="order-steps">
      {#each shown.history as h, i (i)}
        <li>{time(h.at)} {STEP[h.state] ?? h.state}</li>
      {/each}
    </ol>
  </Frame>
{/if}

<style>
  .reason {
    margin: 0;
    font-size: var(--text-sm);
    color: var(--color-fg-secondary);
  }
  :global(.fold#fold-others) {
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
  .problem {
    margin: 0;
    font-size: var(--text-sm);
  }
  .buttons {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.75rem;
  }
  .reason a {
    color: inherit;
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  /* The record: time in a quiet left column, a filled mark on a lifeline,
     the step on the right. Every step shown has happened. */
  @media (max-width: 760px) {
    /* The two answers stay under the thumb. */
    .buttons {
      position: fixed;
      inset-inline: 0;
      bottom: 0;
      z-index: 10;
      padding: 0.75rem 1rem calc(0.75rem + env(safe-area-inset-bottom));
      border-top: 1px solid var(--color-border);
      background: var(--color-bg-app);
    }
    .buttons :global(button) {
      min-height: 44px;
    }
  }
</style>
