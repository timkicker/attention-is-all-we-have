<script lang="ts">
  /// One request or standing order, read top to bottom: what the agent asked,
  /// what Validio checked at Valio (with the options it compared, when the
  /// backend has them), the rule that decided, the result, and the proof folded
  /// away. On the desk "How this was checked" stands in the margin: the order
  /// against the limits, what Valio was asked, the sealed record. While it
  /// waits, the owner answers here: Approve asks for the approval code under
  /// the buttons, Reject needs none.
  ///
  /// Motion (plans/003, 007, 010, 011, 021): the title arrives from the clicked row; Approve
  /// opens the code in place and the answer lands as one wave; Proof draws as a chain; the
  /// margin's scale shows where this order landed; Replay walks the whole story once.
  import { tick } from "svelte";
  import { page } from "$app/state";
  import { ChevronRight, Play, Square } from "@lucide/svelte";
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import { agentApi } from "$lib/api/agent";
  import { api, ApiError } from "$lib/api/client";
  import type { ActivityDetail } from "$lib/api/types";
  import { bump } from "$lib/chrome.svelte";
  import { owner, isCode } from "$lib/owner.svelte";
  import VCode from "$lib/v/VCode.svelte";
  import { blurSwap, collapse, fadeOut, reduced, rise } from "$lib/motion";
  import { morph, peek } from "$lib/peek.svelte";
  import { dayHead, dayTime, Empty, Explain, hm, LimitScale, live, Loading, LoadError, money, nb, PageHead, pillOf } from "$lib/v2";
  import Options from "./Options.svelte";

  const id = $derived(page.params.id ?? "");
  const detail = live(() => api.activityItem(id), 2000, () => `item:${id}`);
  const d = $derived(detail.data?.item.id === id ? detail.data : undefined);
  // The title the list already knew, while the detail's own answer is on its way (plans/003).
  const head = $derived(d?.item ?? peek.get(id));
  const missing = $derived(!d && detail.status === 404);
  // The rules this request was decided under can be older than today's: then the link says which they are now.
  const rules = live(() => agentApi.rules().catch(() => null), 2000, () => "rules-raw");
  const later = $derived(d && rules.data && rules.data.passVersion !== d.rule.version ? rules.data.passVersion : null);
  // The options Validio compared: the backend's request view; none for a standing order or in the fixture.
  const req = live(() => (id.startsWith("S-") ? Promise.resolve(null) : api.request(id).catch(() => null)), 2000, () => `request:${id}`);
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
    document.getElementById("proof")?.scrollIntoView({ block: "start", behavior: reduced() ? "auto" : "smooth" });
    glow(document.querySelector("#proof > summary"));
  }
  /** A brief petrol tint on where a link landed (plans/011). */
  function glow(el: Element | null) {
    if (!el) return;
    el.classList.remove("v-glow");
    void (el as HTMLElement).offsetWidth;
    el.classList.add("v-glow");
    setTimeout(() => el.classList.remove("v-glow"), 1600);
  }

  // A hash copies on a click; "Copied" stands in for it a moment (plans/011).
  let copiedHash = $state("");
  let copyTimer: ReturnType<typeof setTimeout> | undefined;
  async function copyHash(h: string) {
    try {
      await navigator.clipboard.writeText(h);
    } catch {
      return;
    }
    copiedHash = h;
    clearTimeout(copyTimer);
    copyTimer = setTimeout(() => (copiedHash = ""), 1600);
  }

  // The result arrived while the page was open: its check draws itself (plans/007).
  let hadResult: boolean | null = null;
  let justDone = $state(false);
  $effect(() => {
    if (!d) return;
    if (hadResult === false && d.result) justDone = true;
    hadResult = !!d.result;
  });

  // Replay (plans/021): the page walks its own story once, step by step; any input stops it.
  let replaying = $state(false);
  let step = $state(0);
  let beat = $state(0); // re-keys the result and the scale's marker so they play again
  let mkBeat = $state(0);
  let replaySaid = $state("");
  let ctl: AbortController | null = null;
  const sleepFor = (ms: number, sig: AbortSignal) =>
    new Promise<void>((res, rej) => {
      const t = setTimeout(res, ms);
      sig.addEventListener("abort", () => (clearTimeout(t), rej(new Error("stopped"))), { once: true });
    });
  function into(sel: string) {
    const el = document.querySelector(sel);
    if (!el) return;
    const r = el.getBoundingClientRect();
    if (r.top < 72 || r.bottom > innerHeight) el.scrollIntoView({ block: "nearest", behavior: reduced() ? "auto" : "smooth" });
  }
  async function replay() {
    if (replaying) return stopReplay();
    ctl = new AbortController();
    const sig = ctl.signal;
    const calm = reduced();
    const hold = calm ? 1200 : 900;
    proofOpen = false;
    replaying = true;
    step = 0;
    replaySaid = "Replaying the decision";
    try {
      await sleepFor(calm ? 0 : 300, sig);
      const steps: [number, string][] = [
        [1, "#h-asked"],
        [2, "#h-checks"],
        [3, "#h-rule"],
        [4, "#h-result"],
        [5, "#proof"],
      ];
      for (const [n, sel] of steps) {
        if (!document.querySelector(sel)) continue;
        step = n;
        if (n === 3) mkBeat += 1;
        if (n === 4) beat += 1;
        if (n === 5) proofOpen = true;
        into(sel);
        await sleepFor((n === 2 ? 900 : 300) + hold, sig);
      }
      replaySaid = "Replay finished";
    } catch {
      replaySaid = "Replay stopped";
    } finally {
      replaying = false;
      step = 0;
      ctl = null;
    }
  }
  function stopReplay() {
    ctl?.abort();
  }
  function interrupt(e: Event) {
    if (!replaying) return;
    if (e.type === "pointerdown" && (e.target as Element | null)?.closest?.("#replay")) return;
    stopReplay();
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
      {#key pill.label}<span class="word tone-{pill.tone}-text" data-testid="detail-status" in:blurSwap={{ y: 4 }}>{pill.label}</span>{/key}.
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

<svelte:window onkeydown={interrupt} onpointerdown={interrupt} onwheel={interrupt} ontouchstart={interrupt} />

<PageHead
  title={missing ? "Not found" : (head?.title ?? "")}
  crumbs={[{ href: "/activity", label: "Activity" }]}
  here={head ? nb(longDay(head.at)) : ""}
  back={{ href: "/activity", label: "Activity" }}
  titleTestid="detail-title"
  morphName={morph.id === id ? "v-title" : undefined}
>
  {#snippet actions()}
    {#if d && d.item.kind === "request" && !d.approval}
      <Button variant="ghost" id="replay" data-testid="replay" onclick={replay} aria-pressed={replaying}>
        {#if replaying}<Square size={13} aria-hidden="true" />Stop{:else}<Play size={13} aria-hidden="true" />Replay{/if}
      </Button>
    {/if}
  {/snippet}
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
<p class="sr-only" role="status" data-testid="replay-status">{replaySaid}</p>

{#if missing}
  <div class="parts"><Empty title="It may belong to another kitchen." detail="Activity lists everything your agent did." /></div>
{:else if detail.error && !d}
  <div class="parts"><LoadError detail={detail.error} /></div>
{:else if !d}
  <div class="parts"><Loading rows={4} /></div>
{:else}
  {#if d.approval}
    <div class="ask notice" data-testid="approval" out:collapse={{ duration: 220 }}>
      <p class="ask-q">Your agent waits for you. Valio holds this price until {until(d.approval.holdUntil)}.</p>
      <!-- While the code is asked, its own Approve and Cancel stand in for these two. -->
      {#if !asking}
        <div class="v-buttons" in:rise={{ y: 6, duration: 200 }}>
          <Button id="approve" data-testid="approve" aria-expanded={false} disabled={busy} onclick={() => (asking = true)}>Approve</Button>
          <Button id="reject" data-testid="reject" variant="outline" disabled={busy} onclick={reject}>Reject</Button>
        </div>
      {/if}
      {#if problem && !asking}<p class="ask-problem" role="alert" in:rise={{ y: 4, duration: 200 }} out:fadeOut>{problem}</p>{/if}
      {#if asking}
        <div in:rise={{ y: 6, duration: 200 }}>
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
    </div>
  {/if}

  <div class="doc" class:v-arrive={detail.arrive}>
    <div class="parts" class:replaying>
      {#if replaying}<span class="replay-line" style:--p={step / 5} aria-hidden="true"></span>{/if}
      <section class="part" class:lit={step >= 1} aria-labelledby="h-asked">
        <h2 class="v-h" id="h-asked">What your agent asked</h2>
        <figure class="asked" data-testid="asked">
          <blockquote>“{nb(d.asked.text)}”</blockquote>
          <figcaption>{d.asked.agentName}</figcaption>
        </figure>
      </section>

      <!-- A request blocked before Valio was asked has nothing checked: no empty section for it. -->
      {#if d.checks.length || r}
        <section class="part" class:lit={step >= 2} aria-labelledby="h-checks">
          <h2 class="v-h" id="h-checks">What Validio checked at Valio</h2>
          {#if d.checks.length}
            <dl class="checks" class:stagger={replaying && step === 2}>
              {#each d.checks as c, n (n)}
                {@render fact(`check-${c.label.toLowerCase()}`, c.label, c.value, c.note, c.ok)}
              {/each}
            </dl>
          {/if}
          {#if r}<Options bind:this={options} req={r} proposed={d.item.status === "blocked"} />{/if}
        </section>
      {/if}

      <section class="part" class:lit={step >= 3} aria-labelledby="h-rule">
        <div class="h-row">
          <h2 class="v-h" id="h-rule">Which rule decided</h2>
          <Explain label="What a Rules version is">Every Rules save signs a new version. Orders show the version they were decided under.</Explain>
        </div>
        <a class="rule-row" href="/rules" id="rule-link" data-testid="rule">
          <span class="rule-text">{nb(d.rule.text)}</span>
          <span class="rule-ver" data-testid="rule-version">{later ? `Rules, version ${d.rule.version} (now ${later})` : `Rules, version ${d.rule.version}`}</span>
        </a>
      </section>

      <section class="part" class:lit={step >= 4} aria-labelledby="h-result">
        <h2 class="v-h" id="h-result">Result</h2>
        {#key beat}
          {#if d.result}
            {@const ids = d.result.orderIds.length ? d.result.orderIds : [d.result.orderId]}
            <dl class="checks" in:rise={{ y: 6, delay: 80 }}>
              <div class="check" data-testid="result-order" data-order={ids.join(", ")}>
                <dt class="ck-label">{ids.length > 1 ? "Orders" : "Order"}</dt>
                <dd class="ck-val ok">
                  <svg class="v-check done-mark" class:just={justDone || beat > 0} viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="M20 6 9 17l-5-5" pathLength="1" /></svg>
                  <span class="ck-value">{ids.length > 1 ? `${ids.length} orders placed with Valio` : "Placed with Valio"}</span>
                </dd>
              </div>
              {#if d.result.delivery}{@render fact("result-delivery", "Delivery", date(d.result.delivery))}{/if}
            </dl>
          {:else}
            <p class="none" data-testid="result-none" in:blurSwap>{NOT_ORDERED[d.item.status]}</p>
          {/if}
        {/key}
      </section>

      <details class="fold proof" class:lit={step >= 5} id="proof" data-testid="proof" bind:open={proofOpen}>
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
                <button type="button" class="pe-hash mono" title={p.hash} aria-label="Copy hash" onclick={() => copyHash(p.hash)}>
                  {#key copiedHash === p.hash}<span class="ph" in:blurSwap={{ duration: 150 }}>{copiedHash === p.hash ? "Copied" : p.hash}</span>{/key}
                </button>
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
          <div class="ck" class:lit={step === 3} data-testid="limits">
            <dt>{limits.total > limits.most ? "Over your limits" : over ? "Above what it orders alone" : "Within your limits"}</dt>
            <dd>
              {#key mkBeat}<LimitScale mode="order" alone={limits.alone} waiting={limits.most} order={limits.total} id="detail-scale" />{/key}
            </dd>
          </div>
        {/if}
        {#if r}
          <div class="ck" class:lit={step === 2}>
            <dt>Valio asked for price and stock</dt>
            <dd>{r.liveChecked.ids} products, prices and stock read before deciding.{#if r.valioText}{" "}{nb(r.valioText)}.{/if}</dd>
          </div>
          {#if chosen?.dietText}
            <div class="ck" class:lit={step === 2}>
              <dt>{chosen.dietText.split(":")[0]} confirmed</dt>
              <dd>{nb(chosen.dietText.split(/:\s*/)[1] ?? "").replace(/^./, (c) => c.toUpperCase())}.</dd>
            </div>
          {/if}
          {#if planted?.supplierText}
            <div class="ck" class:lit={step === 2}>
              <dt>One supplier text ignored</dt>
              <dd>
                <p>The description of <b>{nb(planted.displayName ?? planted.name)}</b> tried to instruct your agent. It never reached the agent.</p>
                <blockquote data-raw>{planted.supplierText.text}</blockquote>
                <a class="link" href="#option-{planted.productId}" onclick={(e) => { e.preventDefault(); options?.show(planted.productId); }}>Show this product</a>
              </dd>
            </div>
          {/if}
        {/if}
        <div class="ck" class:lit={step === 5}>
          <dt>Recorded in your activity <Explain label="What sealed means">Each entry carries the fingerprint of the one before. A changed entry breaks the chain.</Explain></dt>
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
  @media (hover: hover) and (pointer: fine) {
    .rule-row:hover .rule-text {
      color: var(--valio);
    }
  }
  .rule-row {
    transition: background-color var(--duration-fast) ease;
  }
  .rule-row:active {
    background: var(--v-tint-fill);
    transition-duration: 0ms;
  }
  .rule-row:focus-visible {
    outline-offset: -2px;
    background: var(--v-tint-hover);
  }
  .rule-row:focus-visible .rule-text {
    color: var(--valio);
  }
  .h-row {
    display: flex;
    align-items: baseline;
    gap: 4px;
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
    display: inline-grid;
    justify-items: start;
    padding: 0;
    border: 0;
    background: none;
    font: inherit;
    font-family: var(--font-mono);
    font-size: var(--fs-cap);
    line-height: 16px;
    text-align: left;
    color: var(--v-faint);
    overflow-wrap: anywhere;
    text-decoration: underline;
    text-decoration-color: transparent;
    text-underline-offset: 3px;
    transition:
      text-decoration-color var(--duration-fast) ease,
      color var(--duration-fast) ease;
  }
  .pe-hash .ph {
    grid-area: 1 / 1;
  }
  @media (hover: hover) and (pointer: fine) {
    .pe-hash:hover {
      color: var(--v-muted);
      text-decoration-color: currentColor;
    }
  }
  .pe-hash:focus-visible {
    border-radius: var(--radius-chip);
  }

  /* The chain (plans/011): a line through the entries, a node on each; on opening the line
     draws down while the entries fall into place just behind it. */
  .pes {
    position: relative;
    padding-left: 20px;
  }
  .pes::before {
    content: "";
    position: absolute;
    left: 3px;
    top: 20px;
    bottom: 20px;
    width: 1px;
    background: var(--v-line-strong);
    transform-origin: top;
  }
  .pe {
    position: relative;
  }
  .pe::before {
    content: "";
    position: absolute;
    left: -20px;
    top: 17px;
    width: 7px;
    height: 7px;
    border: 1.5px solid var(--valio);
    border-radius: var(--radius-chip);
    background: var(--v-ground);
  }
  details.proof[open] .pes::before {
    animation: v-chain 300ms var(--v-ease-out) both;
  }
  details.proof[open] .pe {
    animation: v-pe 220ms var(--v-ease-out) both;
    animation-delay: 90ms;
  }
  details.proof[open] .pe:nth-child(1) {
    animation-delay: 0ms;
  }
  details.proof[open] .pe:nth-child(2) {
    animation-delay: 30ms;
  }
  details.proof[open] .pe:nth-child(3) {
    animation-delay: 55ms;
  }
  details.proof[open] .pe:nth-child(4) {
    animation-delay: 75ms;
  }
  @keyframes v-chain {
    from {
      transform: scaleY(0);
    }
  }
  @keyframes v-pe {
    from {
      opacity: 0;
      transform: translateY(4px);
    }
  }

  /* The result's check (plans/007). */
  .done-mark {
    flex: none;
    align-self: center;
  }

  /* Replay (plans/021): everything not yet reached dims; a petrol line measures the way. */
  .parts {
    position: relative;
  }
  .parts > :is(.part, .proof),
  .checked .ck {
    transition: opacity 300ms var(--v-ease-out);
  }
  .parts.replaying > :is(.part, .proof):not(.lit),
  .parts.replaying ~ .checked .ck:not(.lit) {
    opacity: 0.32;
  }
  .replay-line {
    position: absolute;
    left: -16px;
    top: 0;
    bottom: 0;
    width: 2px;
    background: var(--valio);
    transform-origin: top;
    transform: scaleY(var(--p));
    transition: transform 300ms var(--v-ease-in-out);
  }
  .checks.stagger > .check {
    animation: v-pe 220ms var(--v-ease-out) both;
  }
  .checks.stagger > .check:nth-child(2) {
    animation-delay: 120ms;
  }
  .checks.stagger > .check:nth-child(3) {
    animation-delay: 220ms;
  }
  .checks.stagger > .check:nth-child(4) {
    animation-delay: 310ms;
  }
  .checks.stagger > .check:nth-child(n + 5) {
    animation-delay: 390ms;
  }
  @media (prefers-reduced-motion: reduce) {
    details.proof[open] .pes::before {
      animation: none;
    }
    details.proof[open] .pe,
    .checks.stagger > .check {
      animation: v-fade-in 120ms linear both;
      animation-delay: 0ms;
    }
    .replay-line {
      transition: none;
    }
  }

  /* How this was checked: the margin column. */
  .checked {
    position: sticky;
    top: 84px; /* below the sticky band */
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
    .replay-line {
      left: -8px;
    }
    .checked {
      top: 64px;
    }
    .parts {
      gap: 32px;
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
