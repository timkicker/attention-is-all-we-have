<script lang="ts">
  /// The owner's one decision, on the phone: the question as the h1, the
  /// Total lane, what is ordered instead of what, the others folded, and a
  /// pinned bar with Reject and Approve. The code is asked only when the
  /// server wants one.
  import { tick } from "svelte";
  import { page } from "$app/state";
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import { Section } from "@arlen/ui-kit/components/ui/section";
  import { ChevronRight } from "@lucide/svelte";
  import { ApiError, api } from "$lib/api/client";
  import type { Order } from "$lib/api/types";
  import { bump } from "$lib/chrome.svelte";
  import { day, hm, money, nb } from "$lib/format";
  import { live } from "$lib/live.svelte";
  import { isCode, owner } from "$lib/owner.svelte";
  import { optionLine } from "$lib/v";
  import VCode from "$lib/v/VCode.svelte";
  import VHead from "$lib/v/VHead.svelte";
  import VLane from "$lib/v/VLane.svelte";
  import VPill from "$lib/v/VPill.svelte";
  import VPlotTotal from "$lib/v/VPlotTotal.svelte";
  import VState from "$lib/v/VState.svelte";
  import VValueRow from "$lib/v/VValueRow.svelte";

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
  const pass = live(() => api.spendPass("M-1"));
  const demo = live(() => api.demoState());

  let done = $state<Order | undefined>();
  let step = $state<null | "approve" | "reject">(null);
  let code = $state("");
  let wrong = $state("");
  let busy = $state(false);
  let problem = $state("");

  const o = $derived(done ?? order.data);
  const r = $derived(req.data);
  const l = $derived(o?.lines[0]);
  const rid = $derived(o?.requestId ?? r?.id ?? id);
  const need = $derived(r?.lines[0]);
  const all = $derived(need ? [...need.options, ...(need.substitutes ?? []), ...(need.beyondList ?? [])] : []);
  // The asked-for product stands apart (askedFor); older answers still list it among the options.
  const askedName = $derived(r?.askedFor?.displayName ?? (() => { const a = all.find((x) => x.productId === need?.need.productId); return a ? (a.displayName ?? a.name) : undefined; })());
  const chosenOpt = $derived(all.find((x) => x.productId === l?.productId));
  const others = $derived(all.filter((x) => x.productId !== l?.productId && x.productId !== need?.need.productId));
  // The lactose fact: a measured value when Valio gives one, else its lactose-free claim.
  /** The done heading names the product: "10 × 2.5 kg of mozzarella-fontal
   *  crumbled cheese", from the question, or the line's name. */
  function doneWhat(x: Order, placed = true): string {
    // Not ordered: the product's display name alone, so the title stays on one line.
    const d = x.lines[0]?.displayName;
    if (!placed && d) return d.length > 1 && d[1] === d[1].toLowerCase() ? d.charAt(0).toLowerCase() + d.slice(1) : d;
    const q = /^Order (.+?) for .+\?$/.exec(x.questionText ?? "")?.[1];
    if (q) return q;
    const n = x.lines[0]?.displayName ?? x.lines[0]?.name ?? "the order";
    return /^\S+ [a-z]/.test(n) ? n.charAt(0).toLowerCase() + n.slice(1) : n;
  }
  /** The done steps with their times from the order's history, as the ledger shows them. */
  const STEP: Record<string, string> = { waiting: "Asked you", approved: "You approved", placed: "Validio placed the order", rejected: "You rejected" };
  function steps(x: Order, placed: boolean): { what: string; time: string }[] {
    const want = placed ? ["waiting", "approved", "placed"] : ["waiting", "rejected"];
    return want.map((state) => {
      const h = x.history.find((e) => e.state === state);
      return { what: STEP[state], time: h ? (h.timeText ?? hm(h.at)) : "" };
    });
  }
  const lactose = $derived(chosenOpt?.facts.find((f) => f.field === "lactose") ?? chosenOpt?.facts.find((f) => f.field === "claim:FREE_FROM_LACTOSE"));
  const upper = (t: string) => t.charAt(0).toUpperCase() + t.slice(1);
  const sim = $derived(r?.simulated?.[0]);
  const codeRequired = $derived(!!demo.data?.codeRequired);
  const waiting = $derived(o?.state === "waiting");

  async function press(kind: "approve" | "reject") {
    problem = "";
    wrong = "";
    if (codeRequired && !isCode(owner.code)) {
      step = kind;
      return;
    }
    if (kind === "reject" && step !== "reject") {
      step = "reject";
      await tick();
      document.getElementById("confirm-reject")?.focus();
      return;
    }
    await decide(kind);
  }

  async function submitCode() {
    if (!step) return;
    if (!isCode(code)) {
      wrong = "Wrong code. Try again.";
      return;
    }
    owner.code = code;
    await decide(step);
  }

  async function decide(kind: "approve" | "reject") {
    if (!o || busy) return;
    busy = true;
    try {
      done = await (kind === "approve" ? api.approve(o.id) : api.reject(o.id));
      step = null;
      bump();
      window.scrollTo({ top: 0 });
    } catch (e) {
      const status = e instanceof ApiError ? e.status : 0;
      if (status === 403) {
        owner.code = "";
        wrong = "Wrong code. Try again.";
      } else if (status === 409) {
        problem = "Already placed. Nothing changed.";
        step = null;
      } else problem = e instanceof Error ? e.message : String(e);
    } finally {
      busy = false;
    }
  }

  const cancel = () => {
    step = null;
    wrong = "";
  };
</script>

{#if !o}
  {#if order.error}
    <VHead title="Approve" crumbs={[{ href: "/", label: "Inbox" }]} here="Approve" back={{ href: "/", label: "Inbox" }} menu={false} />
    <VState kind="error" title={/404|not found/i.test(order.error) ? `No request ${id}.` : "Validio is not reachable."} detail={order.error} onretry={() => location.reload()} />
  {:else}
    <VState kind="loading" rows={3} />
  {/if}
{:else if !waiting}
  {@const placed = o.state === "placed" || o.state === "approved"}
  {@const what = doneWhat(o, placed)}
  <VHead
    title={placed ? `Ordered ${what}` : `Not ordered: ${what}`}
    crumbs={[{ href: "/", label: "Inbox" }, { href: `/requests/${rid}`, label: rid }]}
    here="Approve"
    back={{ href: `/requests/${rid}`, label: "Request" }}
    menu={false}
  >
    {#snippet facts()}
      <VPill label={placed ? "Placed" : "Rejected"} tone={placed ? "ok" : "bad"} />
      <b class="num">{o.moneyText ?? money(o.totalCents)}</b>
      {#if placed}<a href="/ledger">Order {o.id} ›</a>{/if}
    {/snippet}
    {#if problem}<p class="lead" role="status">{problem}</p>{/if}
    <p class="lead">{placed ? "Price and delivery confirmed again before ordering." : "Nothing was ordered."}</p>
  </VHead>
  <ol class="steps" data-testid="order-steps" id="order-steps">
    {#each steps(o, placed) as st (st.what)}
      <li><span class="t num">{st.time}</span><span>{st.what}</span></li>
    {/each}
  </ol>
{:else}
  <VHead
    title={o.questionText ?? r?.question ?? `Order for ${money(o.totalCents)}?`}
    titleId="question"
    titleTestid="approve-question"
    crumbs={[{ href: "/", label: "Inbox" }, { href: `/requests/${rid}`, label: rid }]}
    here="Approve"
    back={{ href: `/requests/${rid}`, label: "Request" }}
    menu={false}
  >
    {#snippet facts()}
      <span>Deliver by {day(o.deliverBy)}</span>
      {#if l?.isSubstitute && !l.onValioList}<span>Not on Valio's list</span>{/if}
    {/snippet}
  </VHead>

  <div class="blocks decide">
    <div>
      <VLane name="Total" value={o.moneyText ?? money(o.totalCents)} sub={o.usedBeforeCents ? `${money(o.usedBeforeCents)} ordered before` : undefined}>
        {#snippet plot()}
          <VPlotTotal before={o.usedBeforeCents ?? 0} amount={o.totalCents} auto={pass.data?.autoLimitCents} cap={pass.data?.hardCapCents} />
        {/snippet}
      </VLane>
    </div>

    {#if l}
      <Section class="v-card">
        <VValueRow label="Product" value={l.displayName ?? l.name} sub={l.qtyText} />
        {#if askedName}
          <VValueRow label="Instead of" value="{askedName}{sim ? ', out of stock (simulated)' : ''}" testid="instead-of" />
        {/if}
        {#if lactose}
          <VValueRow label="Lactose" value="{upper(lactose.valueText ?? String(lactose.value ?? ''))}{lactose.grade === 'attested' || lactose.grade === 'consistent' ? ', checked' : ''}" />
        {/if}
      </Section>
    {/if}

    {#if others.length}
      <details class="fold others" data-testid="others" id="others">
        <summary><ChevronRight class="chev" aria-hidden="true" />Why not the others <span class="num">{others.length}</span></summary>
        <ul class="fold-body">
          {#each others as x (x.productId)}
            <li><b>{nb(x.displayName ?? x.name)}</b> {optionLine(x)}</li>
          {/each}
        </ul>
      </details>
    {/if}

    {#if step && codeRequired && !isCode(owner.code)}
      <VCode bind:value={code} error={wrong} onsubmit={submitCode} />
    {/if}
    {#if problem}<p class="q-sub" role="alert">{problem}</p>{/if}

    <div class="bar">
      {#if step === "reject" && !(codeRequired && !isCode(owner.code))}
        <Button variant="outline" onclick={cancel}>Cancel</Button>
        <Button id="confirm-reject" data-testid="code-submit" disabled={busy} onclick={() => decide("reject")}>{busy ? "Rejecting…" : "Confirm rejection"}</Button>
      {:else if step}
        <Button variant="outline" onclick={cancel}>Cancel</Button>
        <Button data-testid="code-submit" id="code-submit" disabled={busy} onclick={submitCode}>
          {busy ? (step === "approve" ? "Approving…" : "Rejecting…") : step === "approve" ? "Confirm approval" : "Confirm rejection"}
        </Button>
      {:else}
        <Button variant="outline" data-testid="reject" id="reject" disabled={busy} onclick={() => press("reject")}>Reject</Button>
        <Button data-testid="approve" id="approve" disabled={busy} onclick={() => press("approve")}>{busy ? "Approving…" : "Approve"}</Button>
      {/if}
    </div>
  </div>
{/if}

<style>
  .others .fold-body {
    margin: 8px 0 0;
    padding: 0;
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .others b {
    font-weight: 500;
    color: var(--v-fg);
  }
  .bar {
    display: flex;
    gap: 8px;
    margin-top: 24px;
  }
  .steps {
    margin: 32px 0 0;
    padding: 0;
    list-style: none;
    border-top: 1px solid var(--v-line);
  }
  .steps li {
    display: grid;
    grid-template-columns: 176px minmax(0, 1fr);
    gap: 24px;
    padding: 12px 0;
    border-bottom: 1px solid var(--v-line);
    font-size: var(--fs-body);
    line-height: var(--lh-body);
  }
  .steps .t {
    font-size: var(--fs-meta);
    color: var(--v-muted);
  }
  @media (max-width: 760px) {
    .steps li {
      grid-template-columns: 48px minmax(0, 1fr);
      gap: 16px;
    }
    .bar {
      position: fixed;
      left: 0;
      right: 0;
      bottom: 0;
      z-index: 20;
      margin: 0;
      padding: 12px 16px calc(12px + env(safe-area-inset-bottom));
      background: var(--v-app);
      border-top: 1px solid var(--v-line);
    }
    .bar :global([data-slot="button"]) {
      flex: 1;
    }
    /* At 390×844 the whole decision, down to "Why not the others", fits above
       the pinned bar with 16 px to spare, without scrolling. */
    .decide {
      margin-top: 24px;
    }
    .decide > :global(* + *) {
      margin-top: 16px;
    }
  }
</style>
