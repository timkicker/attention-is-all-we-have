<script lang="ts">
  /// One request or standing order, read top to bottom: what the agent asked,
  /// what Validio checked at Valio, the rule that decided, the result, and the
  /// proof folded away. While it waits, the owner answers here: Approve asks
  /// for the approval code under the buttons, Reject needs none.
  import { tick } from "svelte";
  import { page } from "$app/state";
  import { Check, ChevronRight, X } from "@lucide/svelte";
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import { Section } from "@arlen/ui-kit/components/ui/section";
  import { api, ApiError } from "$lib/api/client";
  import type { ActivityDetail } from "$lib/api/types";
  import { bump } from "$lib/chrome.svelte";
  import { owner, isCode } from "$lib/owner.svelte";
  import VCode from "$lib/v/VCode.svelte";
  import { dayHead, dayTime, Empty, hm, live, Loading, LoadError, money, nb, PageHead, StatusPill } from "$lib/v2";

  const id = $derived(page.params.id ?? "");
  const detail = live(() => api.activityItem(id));
  const d = $derived(detail.data?.item.id === id ? detail.data : undefined);
  const missing = $derived(!d && detail.status === 404);

  const HELSINKI = "Europe/Helsinki";
  const date = (ymd: string) =>
    nb(new Intl.DateTimeFormat("en-GB", { weekday: "short", day: "numeric", month: "short", timeZone: HELSINKI }).format(new Date(`${ymd}T12:00:00Z`)));
  /** "15:00 today" or "Mon 16 Nov, 15:00". */
  const until = (iso: string) => (dayHead(iso).startsWith("Today") ? `${hm(iso)} today` : dayTime(iso));
  const secs = (iso: string) =>
    new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit", timeZone: HELSINKI }).format(new Date(iso));

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

{#snippet facts()}
  {#if d}
    <StatusPill item={d.item} testid="detail-status" />
    {#if d.item.totalCents != null}<b class="num" data-testid="detail-total">{nb(money(d.item.totalCents))}</b>{/if}
    <span>{dayTime(d.item.at)}</span>
  {/if}
{/snippet}

<PageHead
  title={d?.item.title ?? id}
  crumbs={[{ href: "/activity", label: "Activity" }]}
  here={id}
  back={{ href: "/activity", label: "Activity" }}
  titleTestid="detail-title"
  facts={d ? facts : undefined}
/>

{#snippet fact(testid: string, label: string, value: string, note: string | null = null, ok: boolean | null = null)}
  <div class="check" data-testid={testid} data-ok={ok}>
    <span class="ck-mark" class:ok={ok === true} class:bad={ok === false}>
      {#if ok === true}
        <Check size={16} strokeWidth={2} aria-hidden="true" /><span class="sr-only">Passed:</span>
      {:else if ok === false}
        <X size={16} strokeWidth={2} aria-hidden="true" /><span class="sr-only">Failed:</span>
      {/if}
    </span>
    <span class="ck-label">{label}</span>
    <span class="ck-val">
      <span class="ck-value">{nb(value)}</span>
      {#if note}<span class="ck-note">{nb(note)}</span>{/if}
    </span>
  </div>
{/snippet}

<p class="sr-only" role="status">{said}</p>

<div class="parts">
  {#if missing}
    <Empty title="Not found" detail="It may belong to another kitchen. Activity lists everything your agent did." />
  {:else if detail.error && !d}
    <LoadError detail={detail.error} />
  {:else if !d}
    <Loading rows={4} />
  {:else}
    {#if d.approval}
      <Section class="v-card">
        <div class="ask" data-testid="approval">
          <p class="ask-q">Your agent waits for you. Valio holds this price until {until(d.approval.holdUntil)}.</p>
          <!-- While the code is asked, its own Approve and Cancel stand in for these two. -->
          {#if !asking}
            <div class="v-buttons">
              <Button id="approve" data-testid="approve" aria-expanded={false} disabled={busy} onclick={() => (asking = true)}>Approve</Button>
              <Button id="reject" data-testid="reject" variant="outline" disabled={busy} onclick={reject}>Reject</Button>
            </div>
          {/if}
          {#if problem && !asking}<p class="ask-problem" role="alert">{problem}</p>{/if}
        </div>
        {#if asking}
          <div class="ask">
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
          </div>
        {/if}
      </Section>
    {/if}

    <section class="part" aria-labelledby="h-asked">
      <h2 class="v-h" id="h-asked">What your agent asked</h2>
      <Section class="v-card">
        <figure class="asked" data-testid="asked">
          <blockquote>“{nb(d.asked.text)}”</blockquote>
          <figcaption>{d.asked.agentName}</figcaption>
        </figure>
      </Section>
    </section>

    <!-- A request blocked before Valio was asked has nothing checked: no empty card for it. -->
    {#if d.checks.length}
    <section class="part" aria-labelledby="h-checks">
      <h2 class="v-h" id="h-checks">What Validio checked at Valio</h2>
      <Section class="v-card">
        {#each d.checks as c, n (n)}
          {@render fact(`check-${c.label.toLowerCase()}`, c.label, c.value, c.note, c.ok)}
        {/each}
      </Section>
    </section>
    {/if}

    <section class="part" aria-labelledby="h-rule">
      <h2 class="v-h" id="h-rule">Which rule decided</h2>
      <Section class="v-card">
        <a class="rule-row" href="/rules" id="rule-link" data-testid="rule">
          <span class="rule-text">{nb(d.rule.text)}</span>
          <span class="rule-ver">Rules, version {d.rule.version}</span>
          <ChevronRight class="go" size={16} strokeWidth={1.75} aria-hidden="true" />
        </a>
      </Section>
    </section>

    <section class="part" aria-labelledby="h-result">
      <h2 class="v-h" id="h-result">Result</h2>
      <Section class="v-card">
        {#if d.result}
          {@const ids = d.result.orderIds.length ? d.result.orderIds : [d.result.orderId]}
          {@render fact("result-order", ids.length > 1 ? "Valio orders" : "Valio order", ids.join(", "))}
          {#if d.result.delivery}{@render fact("result-delivery", "Delivery", date(d.result.delivery))}{/if}
        {:else}
          <p class="none" data-testid="result-none">{NOT_ORDERED[d.item.status]}</p>
        {/if}
      </Section>
    </section>

    <details class="fold proof" id="proof" data-testid="proof">
      <summary id="proof-toggle">
        <ChevronRight class="chev" aria-hidden="true" />
        <span class="proof-name">Proof</span>
        <span class="proof-n">{d.proof.length} {d.proof.length === 1 ? "entry" : "entries"}</span>
      </summary>
      <Section class="v-card">
        {#each d.proof as p (p.hash)}
          <div class="pe" data-raw>
            <span class="pe-time num">{secs(p.at)}</span>
            <span class="pe-actor">{p.actor}</span>
            <span class="pe-main">
              <span class="pe-text">{p.text}</span>
              <span class="pe-hash mono">{p.hash}</span>
            </span>
          </div>
        {/each}
      </Section>
    </details>
  {/if}
</div>

<style>
  .parts {
    display: flex;
    flex-direction: column;
    gap: 32px;
    margin-top: 32px;
  }
  .part {
    display: flex;
    flex-direction: column;
  }
  .part .v-h {
    margin: 0;
  }

  /* The answer */
  .ask {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 16px;
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

  /* Asked */
  .asked {
    margin: 0;
    padding: 12px 16px;
  }
  .asked blockquote {
    margin: 0;
    font-size: var(--fs-body);
    line-height: var(--lh-body);
  }
  .asked figcaption {
    margin-top: 4px;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-muted);
  }

  /* Checks */
  .check {
    display: grid;
    grid-template-columns: 16px 152px minmax(0, 1fr);
    column-gap: 12px;
    align-items: baseline;
    min-height: 48px;
    padding: 12px 16px;
  }
  .ck-mark {
    display: flex;
    align-self: center;
    color: var(--v-faint);
  }
  .ck-mark.ok {
    color: var(--v-ok-text);
  }
  .ck-mark.bad {
    color: var(--v-bad-text);
  }
  .ck-label {
    font-size: var(--fs-meta);
    line-height: var(--lh-body);
    color: var(--v-muted);
  }
  .ck-val {
    display: flex;
    flex-wrap: wrap;
    column-gap: 8px;
    min-width: 0;
  }
  .ck-value {
    font-size: var(--fs-body);
    line-height: var(--lh-body);
    font-weight: 500;
    overflow-wrap: anywhere;
  }
  .check[data-ok="false"] .ck-value {
    color: var(--v-bad-text);
  }
  .ck-note {
    font-size: var(--fs-meta);
    line-height: var(--lh-body);
    color: var(--v-muted);
  }

  /* Rule */
  .rule-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto auto;
    align-items: baseline;
    column-gap: 12px;
    min-height: 48px;
    padding: 12px 16px;
    color: inherit;
    text-decoration: none;
    border-radius: max(0px, calc(var(--radius-card) - 1px));
    transition: background-color var(--duration-fast) ease;
  }
  .rule-row:hover {
    background: var(--v-tint-hover);
  }
  .rule-text {
    font-size: var(--fs-body);
    line-height: var(--lh-body);
    font-weight: 500;
  }
  .rule-ver {
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-muted);
    white-space: nowrap;
  }
  .rule-row :global(.go) {
    align-self: center;
    color: var(--v-faint);
  }

  .none {
    margin: 0;
    padding: 12px 16px;
    font-size: var(--fs-body);
    line-height: var(--lh-body);
    color: var(--v-muted);
  }

  /* Proof */
  .proof > summary {
    font-size: var(--fs-head);
  }
  .proof-name {
    color: var(--v-fg);
    font-weight: 600;
  }
  .proof-n {
    margin-left: 4px;
    color: var(--v-faint);
  }
  .proof[open] > summary {
    margin-bottom: 8px;
  }
  .pe {
    display: grid;
    grid-template-columns: 72px 112px minmax(0, 1fr);
    column-gap: 12px;
    align-items: baseline;
    padding: 12px 16px;
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
  }
  .pe-actor {
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    font-weight: 500;
  }
  .pe-hash {
    font-size: var(--fs-cap);
    line-height: 16px;
    color: var(--v-faint);
    overflow-wrap: anywhere;
  }

  @media (max-width: 760px) {
    /* Six digits need no more; Cancel and Confirm then stay on the field's line. */
    .ask :global(.vcode .code) {
      max-width: 128px;
    }
    .check {
      grid-template-columns: 16px minmax(0, 1fr);
      row-gap: 0;
    }
    .ck-mark {
      grid-row: 1 / span 2;
      align-self: start;
      padding-top: 2px;
    }
    .ck-label {
      line-height: var(--lh-meta);
    }
    .ck-val {
      grid-column: 2;
    }
    .rule-row {
      grid-template-columns: minmax(0, 1fr) auto;
      row-gap: 4px;
    }
    .rule-text {
      grid-column: 1;
    }
    .rule-ver {
      grid-column: 1;
      grid-row: 2;
    }
    .rule-row :global(.go) {
      grid-column: 2;
      grid-row: 1 / span 2;
    }
    .pe {
      grid-template-columns: auto minmax(0, 1fr);
      row-gap: 2px;
    }
    .pe-main {
      grid-column: 1 / -1;
    }
  }
</style>
