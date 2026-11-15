<script lang="ts">
  /// One request or standing order, read top to bottom: what the agent asked,
  /// what Validio checked at Valio (with the options it compared, when the
  /// backend has them), the rule that decided, the result, and the proof folded
  /// away. On the desk "How this was checked" stands in the margin: the order
  /// against the limits, what Valio was asked, the sealed record. While it
  /// waits, the owner answers here: Approve asks for the approval code under
  /// the buttons, Reject needs none.
  import { tick } from "svelte";
  import { page } from "$app/state";
  import { ChevronRight } from "@lucide/svelte";
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import { agentApi } from "$lib/api/agent";
  import { api, ApiError } from "$lib/api/client";
  import type { ActivityDetail } from "$lib/api/types";
  import { bump } from "$lib/chrome.svelte";
  import { owner, isCode } from "$lib/owner.svelte";
  import VCode from "$lib/v/VCode.svelte";
  import { dayHead, dayTime, Empty, hm, live, Loading, LoadError, money, nb, PageHead, pillOf } from "$lib/v2";
  import Options from "./Options.svelte";

  const id = $derived(page.params.id ?? "");
  const detail = live(() => api.activityItem(id));
  const d = $derived(detail.data?.item.id === id ? detail.data : undefined);
  const missing = $derived(!d && detail.status === 404);
  // The rules this request was decided under can be older than today's: then the link says which they are now.
  const rules = live(() => agentApi.rules().catch(() => null));
  const later = $derived(d && rules.data && rules.data.passVersion !== d.rule.version ? rules.data.passVersion : null);
  // The options Validio compared: the backend's request view; none for a standing order or in the fixture.
  const req = live(() => (id.startsWith("S-") ? Promise.resolve(null) : api.request(id).catch(() => null)));
  const r = $derived(d?.item.kind === "request" && req.data?.id === id ? req.data : undefined);
  const chosen = $derived(r?.lines[0] ? [...r.lines[0].options, ...(r.lines[0].substitutes ?? []), ...(r.lines[0].beyondList ?? [])].find((o) => o.verdict === "chosen") : undefined);
  const planted = $derived(
    r?.lines.flatMap((l) => [...l.options, ...(l.substitutes ?? []), ...(l.beyondList ?? [])]).find((o) => o.supplierText?.planted || o.supplierText?.reader?.flags.some((f) => f.code === "addresses_agents")),
  );
  let options = $state<Options>();

  const pill = $derived(d ? pillOf(d.item) : undefined);
  // The order against the limits it was decided under; only while those are still today's rules.
  const limits = $derived(
    d && d.item.kind === "request" && d.item.totalCents != null && rules.data?.saved && !later
      ? { total: d.item.totalCents, alone: rules.data.aloneUpToCents, most: rules.data.approvalUpToCents }
      : null,
  );
  const scale = $derived(limits ? Math.max(1, limits.most * 1.06, limits.total) : 1);
  const pct = (c: number) => `${Math.min(100, (c / scale) * 100)}%`;
  /** "1,010 €": whole euros under the meter, cents only where they are not zero. */
  const short = (c: number) => (c % 100 ? money(c) : `${(c / 100).toLocaleString("en-GB")}\u00a0€`);
  const longDay = (iso: string) =>
    new Intl.DateTimeFormat("en-GB", { weekday: "long", day: "numeric", month: "long", timeZone: "Europe/Helsinki" }).format(new Date(iso)).replace(",", "");

  const HELSINKI = "Europe/Helsinki";
  const date = (ymd: string) =>
    nb(new Intl.DateTimeFormat("en-GB", { weekday: "short", day: "numeric", month: "short", timeZone: HELSINKI }).format(new Date(`${ymd}T12:00:00Z`)));
  /** "15:00 today" or "Mon 16 Nov, 15:00". */
  const until = (iso: string) => (dayHead(iso).startsWith("Today") ? `${hm(iso)} today` : dayTime(iso));
  const secs = (iso: string) =>
    new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit", timeZone: HELSINKI }).format(new Date(iso));

  let proofOpen = $state(false);
  async function toProof(e: MouseEvent) {
    e.preventDefault();
    proofOpen = true;
    await tick();
    document.getElementById("proof")?.scrollIntoView({ block: "start", behavior: "smooth" });
  }

  const NOT_ORDERED: Record<ActivityDetail["item"]["status"], string> = {
    waiting: "Not ordered yet",
    blocked: "Nothing ordered",
    standing: "No run yet",
    ordered: "Ordered",
  };

  // The answer: Approve opens the code field, Confirm sends it, Reject goes at once.
  let asking = $state(false);
  let code = $state("");
  let problem = $state("");
  let busy = $state(false);
  let said = $state("");

  // Another item, or the answer came from somewhere else: the field closes.
  $effect(() => {
    if (!d?.approval) {
      asking = false;
      code = "";
      problem = "";
    }
  });

  function why(e: unknown): string {
    if (e instanceof ApiError && e.status === 403) return "That code is not right";
    if (e instanceof ApiError && e.status === 409) return "Someone already answered this";
    return e instanceof Error ? e.message : String(e);
  }

  async function confirm() {
    if (!d?.approval || busy) return;
    if (!isCode(code.trim())) {
      problem = "The code has 6 digits";
      return;
    }
    busy = true;
    problem = "";
    owner.code = code.trim();
    try {
      await api.approve(d.approval.orderId);
      said = "Approved, Valio places the order";
      bump();
    } catch (e) {
      problem = why(e);
      // Answered elsewhere meanwhile: close the code and read the request again.
      if (e instanceof ApiError && e.status === 409) {
        asking = false;
        code = "";
        bump();
      }
    } finally {
      busy = false;
    }
  }

  async function reject() {
    if (!d?.approval || busy) return;
    busy = true;
    problem = "";
    try {
      await api.reject(d.approval.orderId);
      said = "Rejected, nothing is ordered";
      bump();
    } catch (e) {
      problem = why(e);
    } finally {
      busy = false;
    }
  }
</script>

{#snippet lede()}
  {#if d && pill}
    {@const amount = d.item.totalCents != null ? nb(money(d.item.totalCents)) : ""}
    <p class="lead" data-testid="detail-lede">
      <span class="word tone-{pill.tone}-text" data-testid="detail-status">{pill.label}</span>.
      {#if d.item.status === "waiting"}
        {#if amount}<b class="num" data-testid="detail-total">{amount}</b> is ready to order once you approve.{:else}Ready to order once you approve.{/if}
      {:else if d.item.status === "ordered"}
        {#if amount}<b class="num" data-testid="detail-total">{amount}</b>{#if d.result?.delivery}, arriving {date(d.result.delivery)}{/if}.{/if}
      {:else if d.item.status === "blocked"}
        {#if amount}<b class="num" data-testid="detail-total">{amount}</b> was not ordered.{:else}Nothing was ordered.{/if}
      {:else}
        {nb(d.item.why)}.
      {/if}
    </p>
    <p class="facts">
      {#if d.item.kind === "standing" && amount}<b class="num" data-testid="detail-total">{amount}</b>{/if}
      <span>{d.item.kind === "standing" ? dayTime(d.item.at) : `Asked ${dayTime(d.item.at)}`}</span>
    </p>
  {/if}
{/snippet}

<PageHead
  title={missing ? "Not found" : (d?.item.title ?? "")}
  crumbs={[{ href: "/activity", label: "Activity" }]}
  here={d ? nb(longDay(d.item.at)) : ""}
  back={{ href: "/activity", label: "Activity" }}
  titleTestid="detail-title"
>
  {@render lede()}
</PageHead>

{#snippet fact(testid: string, label: string, value: string, note: string | null = null, ok: boolean | null = null)}
  <div class="check" data-testid={testid} data-ok={ok}>
    <dt class="ck-label">{label}</dt>
    <dd class="ck-val" class:ok={ok === true} class:bad={ok === false}>
      {#if ok === true}<span class="sr-only">Passed:</span>{:else if ok === false}<span class="sr-only">Failed:</span>{/if}
      <span class="ck-value">{nb(value)}</span>
      {#if note}<span class="ck-note">{nb(note)}</span>{/if}
    </dd>
  </div>
{/snippet}

<p class="sr-only" role="status">{said}</p>

{#if missing}
  <div class="parts"><Empty title="It may belong to another kitchen." detail="Activity lists everything your agent did." /></div>
{:else if detail.error && !d}
  <div class="parts"><LoadError detail={detail.error} /></div>
{:else if !d}
  <div class="parts"><Loading rows={4} /></div>
{:else}
  {#if d.approval}
    <div class="ask notice" data-testid="approval">
      <p class="ask-q">Your agent waits for you. Valio holds this price until {until(d.approval.holdUntil)}.</p>
      <!-- While the code is asked, its own Approve and Cancel stand in for these two. -->
      {#if !asking}
        <div class="v-buttons">
          <Button id="approve" data-testid="approve" aria-expanded={false} disabled={busy} onclick={() => (asking = true)}>Approve</Button>
          <Button id="reject" data-testid="reject" variant="outline" disabled={busy} onclick={reject}>Reject</Button>
        </div>
      {/if}
      {#if problem && !asking}<p class="ask-problem" role="alert">{problem}</p>{/if}
      {#if asking}
        <VCode
          bind:value={code}
          error={problem}
          {busy}
          submitLabel="Approve"
          onsubmit={confirm}
          oncancel={() => {
            asking = false;
            code = "";
            problem = "";
            tick().then(() => document.getElementById("approve")?.focus());
          }}
        />
      {/if}
    </div>
  {/if}

  <div class="doc">
    <div class="parts">
      <section class="part" aria-labelledby="h-asked">
        <h2 class="v-h" id="h-asked">What your agent asked</h2>
        <figure class="asked" data-testid="asked">
          <blockquote>“{nb(d.asked.text)}”</blockquote>
          <figcaption>{d.asked.agentName}</figcaption>
        </figure>
      </section>

      <!-- A request blocked before Valio was asked has nothing checked: no empty section for it. -->
      {#if d.checks.length || r}
        <section class="part" aria-labelledby="h-checks">
          <h2 class="v-h" id="h-checks">What Validio checked at Valio</h2>
          {#if d.checks.length}
            <dl class="checks">
              {#each d.checks as c, n (n)}
                {@render fact(`check-${c.label.toLowerCase()}`, c.label, c.value, c.note, c.ok)}
              {/each}
            </dl>
          {/if}
          {#if r}<Options bind:this={options} req={r} proposed={d.item.status === "blocked"} />{/if}
        </section>
      {/if}

      <section class="part" aria-labelledby="h-rule">
        <h2 class="v-h" id="h-rule">Which rule decided</h2>
        <a class="rule-row" href="/rules" id="rule-link" data-testid="rule">
          <span class="rule-text">{nb(d.rule.text)}</span>
          <span class="rule-ver" data-testid="rule-version">{later ? `Rules, version ${d.rule.version} (now ${later})` : `Rules, version ${d.rule.version}`}</span>
        </a>
      </section>

      <section class="part" aria-labelledby="h-result">
        <h2 class="v-h" id="h-result">Result</h2>
        {#if d.result}
          {@const ids = d.result.orderIds.length ? d.result.orderIds : [d.result.orderId]}
          <dl class="checks">
            <div class="check" data-testid="result-order" data-order={ids.join(", ")}>
              <dt class="ck-label">{ids.length > 1 ? "Orders" : "Order"}</dt>
              <dd class="ck-val ok"><span class="ck-value">{ids.length > 1 ? `${ids.length} orders placed with Valio` : "Placed with Valio"}</span></dd>
            </div>
            {#if d.result.delivery}{@render fact("result-delivery", "Delivery", date(d.result.delivery))}{/if}
          </dl>
        {:else}
          <p class="none" data-testid="result-none">{NOT_ORDERED[d.item.status]}</p>
        {/if}
      </section>

      <details class="fold proof" id="proof" data-testid="proof" bind:open={proofOpen}>
        <summary id="proof-toggle">
          <ChevronRight class="chev" aria-hidden="true" />
          <span class="proof-name">Proof</span>
          <span class="proof-n">{d.proof.length} {d.proof.length === 1 ? "entry" : "entries"}, sealed</span>
        </summary>
        <ol class="pes">
          {#each d.proof as p (p.hash)}
            <li class="pe" data-raw>
              <span class="pe-time num">{secs(p.at)}</span>
              <span class="pe-actor smallcaps">{p.actor}</span>
              <span class="pe-main">
                <span class="pe-text">{p.text}</span>
                <span class="pe-hash mono">{p.hash}</span>
              </span>
            </li>
          {/each}
        </ol>
      </details>
    </div>

    <aside class="checked" aria-labelledby="h-how">
      <h2 class="v-h" id="h-how">How this was checked</h2>
      <dl>
        {#if limits}
          {@const over = limits.total > limits.alone}
          <div class="ck" data-testid="limits">
            <dt>{limits.total > limits.most ? "Over your limits" : over ? "Above its auto-order limit" : "Within your limits"}</dt>
            <dd>
              <span class="meter" role="img" aria-label="This order {money(limits.total)}. Auto-order up to {money(limits.alone)}. Waiting for you up to {money(limits.most)}.">
                <span class="fill" class:over style:width={pct(limits.total)}></span>
                <span class="tick" style:left={pct(limits.alone)}></span>
              </span>
              <span class="legend num">
                <span>{short(limits.total)}</span>
                <span>{short(limits.alone)} auto-order</span>
                <span>{short(limits.most)} at most</span>
              </span>
            </dd>
          </div>
        {/if}
        {#if r}
          <div class="ck">
            <dt>Valio asked for price and stock</dt>
            <dd>{r.liveChecked.ids} products, prices and stock read before deciding.{#if r.valioText}{" "}{nb(r.valioText)}.{/if}</dd>
          </div>
          {#if chosen?.dietText}
            <div class="ck">
              <dt>{chosen.dietText.split(":")[0]} confirmed</dt>
              <dd>{nb(chosen.dietText.split(/:\s*/)[1] ?? "").replace(/^./, (c) => c.toUpperCase())}.</dd>
            </div>
          {/if}
          {#if planted?.supplierText}
            <div class="ck">
              <dt>One supplier text ignored</dt>
              <dd>
                <p>The description of <b>{nb(planted.displayName ?? planted.name)}</b> tried to instruct your agent. It never reached the agent.</p>
                <blockquote data-raw>{planted.supplierText.text}</blockquote>
                <a class="link" href="#option-{planted.productId}" onclick={(e) => { e.preventDefault(); options?.show(planted.productId); }}>Show this product</a>
              </dd>
            </div>
          {/if}
        {/if}
        <div class="ck">
          <dt>Recorded in your activity</dt>
          <dd>Sealed, nothing changed since. <a class="link" href="#proof" onclick={toProof}>See the proof</a></dd>
        </div>
      </dl>
    </aside>
  </div>
{/if}

<style>
  .doc {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 280px;
    gap: 56px;
    margin-top: 40px;
    align-items: start;
  }
  .parts {
    display: flex;
    flex-direction: column;
    gap: 40px;
    min-width: 0;
  }
  .part {
    display: flex;
    flex-direction: column;
  }

  /* The answer: a calm notice with the petrol rule, the buttons under it. */
  .ask {
    display: flex;
    flex-direction: column;
    gap: 14px;
    margin-top: 28px;
    padding: 4px 0 4px 18px;
  }
  .ask-q {
    margin: 0;
    font-size: var(--fs-body);
    line-height: var(--lh-body);
    font-weight: 500;
  }
  .ask-problem {
    margin: 0;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-bad-text);
  }

  /* Asked: the agent's words as a quotation. */
  .asked {
    margin: 0;
    padding: 2px 0 2px 18px;
    border-left: 2px solid var(--v-line-strong);
  }
  .asked blockquote {
    margin: 0;
    font-family: var(--v-sans);
    font-size: 16px;
    line-height: 25px;
    font-style: normal;
  }
  .asked figcaption {
    margin-top: 6px;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-muted);
  }

  /* Checks and the result: label and value between hairlines; a passed or
     failed value carries a thin rule in its colour. */
  .checks {
    margin: 0;
    border-top: 1px solid var(--v-fg);
  }
  .check {
    display: grid;
    grid-template-columns: 152px minmax(0, 1fr);
    column-gap: 24px;
    align-items: baseline;
    padding: 12px 10px;
    border-bottom: 1px solid var(--v-line);
  }
  .ck-label {
    font-size: var(--fs-meta);
    line-height: var(--lh-body);
    color: var(--v-muted);
  }
  .ck-val {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    column-gap: 10px;
    min-width: 0;
    margin: 0;
  }
  .ck-val.ok,
  .ck-val.bad {
    padding-left: 10px;
    border-left: 2px solid var(--v-ok);
  }
  .ck-val.bad {
    border-left-color: var(--v-bad);
  }
  .ck-value {
    font-size: var(--fs-body);
    line-height: var(--lh-body);
    font-weight: 500;
    overflow-wrap: anywhere;
  }
  .ck-val.bad .ck-value {
    color: var(--v-bad-text);
  }
  .ck-note {
    font-size: var(--fs-meta);
    line-height: var(--lh-body);
    color: var(--v-muted);
  }

  /* Rule: one ruled line, the whole line a link to Rules. */
  .rule-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: baseline;
    column-gap: 24px;
    padding: 14px 10px;
    border-top: 1px solid var(--v-fg);
    border-bottom: 1px solid var(--v-line);
    color: inherit;
    text-decoration: none;
  }
  .rule-text {
    font-size: var(--fs-body);
    line-height: var(--lh-body);
    font-weight: 500;
    transition: color var(--duration-fast) ease;
  }
  .rule-row:hover .rule-text {
    color: var(--valio);
  }
  .rule-ver {
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--valio);
    white-space: nowrap;
  }

  .none {
    margin: 0;
    padding: 14px 10px;
    border-top: 1px solid var(--v-fg);
    border-bottom: 1px solid var(--v-line);
    font-size: var(--fs-body);
    line-height: var(--lh-body);
    color: var(--v-muted);
  }

  /* Proof */
  .proof > summary {
    font-size: var(--fs-head);
  }
  .proof-name {
    font-family: var(--v-sans);
    font-size: var(--fs-section);
    line-height: var(--lh-section);
    font-weight: 600;
    color: var(--v-fg);
  }
  .proof-n {
    margin-left: 6px;
    font-size: var(--fs-meta);
    color: var(--v-faint);
  }
  .pes {
    margin: 12px 0 0;
    padding: 0;
    list-style: none;
    border-top: 1px solid var(--v-fg);
  }
  .pe {
    display: grid;
    grid-template-columns: 72px 112px minmax(0, 1fr);
    column-gap: 16px;
    align-items: baseline;
    padding: 12px 10px;
    border-bottom: 1px solid var(--v-line);
  }
  .pe-time {
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-faint);
  }
  .pe-main {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }
  .pe-text {
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-fg);
  }
  .pe-hash {
    font-size: var(--fs-cap);
    line-height: 16px;
    color: var(--v-faint);
    overflow-wrap: anywhere;
  }

  /* How this was checked: the margin column. */
  .checked {
    position: sticky;
    top: 24px;
    padding: 20px 24px 8px;
    background: var(--v-subtle);
  }
  .checked .v-h {
    font-size: 18px;
    line-height: 26px;
    margin-bottom: 4px;
  }
  .checked dl {
    margin: 0;
  }
  .ck {
    padding: 12px 0 14px;
    border-bottom: 1px solid var(--v-line);
  }
  .ck:last-child {
    border-bottom: 0;
  }
  .ck dt {
    margin-bottom: 2px;
    font-size: var(--fs-head);
    line-height: var(--lh-head);
    font-weight: 500;
  }
  .ck dd {
    margin: 0;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-muted);
  }
  .ck dd p {
    margin: 0;
  }
  .ck dd b {
    font-weight: 500;
    color: var(--v-fg);
  }
  .ck blockquote {
    margin: 10px 0 6px;
    padding: 0 0 0 12px;
    border-left: 2px solid var(--v-bad);
    font-family: var(--v-sans);
    font-size: 14px;
    line-height: 21px;
    font-style: normal;
    color: var(--v-fg);
  }
  .meter {
    position: relative;
    display: block;
    height: 6px;
    margin: 10px 0 6px;
    background: var(--v-line);
  }
  .meter .fill {
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    background: var(--valio);
  }
  .meter .tick {
    position: absolute;
    top: -4px;
    bottom: -4px;
    width: 2px;
    margin-left: -1px;
    background: var(--v-fg);
  }
  .legend {
    display: flex;
    justify-content: space-between;
    gap: 8px;
    font-size: var(--fs-cap);
    white-space: nowrap;
  }

  @media (max-width: 1100px) {
    .doc {
      grid-template-columns: minmax(0, 1fr);
      gap: 40px;
    }
    .checked {
      position: static;
      padding: 16px 16px 4px;
    }
  }
  @media (max-width: 760px) {
    .doc {
      margin-top: 28px;
    }
    .parts {
      gap: 32px;
    }
    /* Six digits need no more; Cancel and Confirm then stay on the field's line. */
    .ask :global(.vcode .code) {
      max-width: 128px;
    }
    .check {
      grid-template-columns: minmax(0, 1fr);
      row-gap: 2px;
      padding: 12px 0;
    }
    .ck-label {
      line-height: var(--lh-meta);
    }
    .rule-row {
      grid-template-columns: minmax(0, 1fr);
      row-gap: 4px;
      padding: 14px 0;
    }
    .none {
      padding: 14px 0;
    }
    .pe {
      grid-template-columns: auto minmax(0, 1fr);
      row-gap: 2px;
      padding: 12px 0;
    }
    .pe-main {
      grid-column: 1 / -1;
    }
  }
</style>
