<script lang="ts">
  /// Home: what needs the owner now and what ran last. Until the first order
  /// came through the agent it is a three step checklist; after that a lede
  /// sentence (what waits, how the agent is), the week's figures, Needs you,
  /// and the newest rows. Live: the page asks again every two seconds, so an
  /// order the agent places shows up without a reload.
  ///
  /// Motion (plans/005, 009, 019): rows the agent adds slide in and glow; figures roll when they
  /// change; the week bar fills; a step done while watching draws its check; finishing setup
  /// while watching brings the figures in as one wave. Nothing moves on a plain visit.
  import { onDestroy, onMount, tick } from "svelte";
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import { agentApi } from "$lib/api/agent";
  import { api, ApiError } from "$lib/api/client";
  import type { ActivityItem, HomeOut } from "$lib/api/types";
  import { bump } from "$lib/chrome.svelte";
  import { blurSwap, buzz, collapse, fadeOut, rise } from "$lib/motion";
  import { net, tick as clock } from "$lib/net.svelte";
  import { isCode, owner, session } from "$lib/owner.svelte";
  import { toast } from "$lib/toast.svelte";
  import VCode from "$lib/v/VCode.svelte";
  import { ActivityRow, ago, Current, ListSection, live, LiveRows, Loading, LoadError, money, nb, PageHead, Ticker, total } from "$lib/v2";

  const home = live(() => api.home(), 2000, () => "home");

  // The most the agent orders alone, for the figures; only once the rules were saved.
  const rules = live(() => agentApi.rules().catch(() => null), 2000, () => "rules-raw");
  const alone = $derived(rules.data?.saved ? rules.data.aloneUpToCents : null);


  // The agent's heartbeat (plans/025, H1): its last call in words, and a beat each time a new call
  // comes in while Home is open.
  onMount(() => clock(15000));
  let beat = $state(0);
  let lastCall: string | null | undefined;
  $effect(() => {
    const at = home.data?.agent.lastUsedAt;
    if (at === undefined) return;
    if (lastCall !== undefined && at && at !== lastCall) beat += 1;
    lastCall = at;
  });

  // Approve from Home (plans/025, H3): the code opens in the row; Reject stays on the item's page.
  let approving = $state<string | null>(null);
  let code = $state("");
  let problem = $state("");
  let busy = $state(false);
  function openApprove(id: string) {
    approving = id;
    code = "";
    problem = "";
  }
  function closeApprove() {
    const id = approving;
    approving = null;
    code = "";
    problem = "";
    if (id) tick().then(() => document.getElementById(`approve-${id}`)?.focus());
  }
  async function approve(i: ActivityItem) {
    if (busy || !i.orderId) return;
    if (!isCode(code.trim())) {
      problem = "The code has 6 digits";
      return;
    }
    busy = true;
    problem = "";
    owner.code = code.trim();
    try {
      await api.approve(i.orderId);
      approving = null;
      code = "";
      buzz();
      toast({ tone: "ok", title: "Approved", body: `${i.title}, ${money(i.totalCents ?? 0)}. Valio places the order.`, action: { href: `/activity/${encodeURIComponent(i.id)}`, label: "See it" } });
      bump();
    } catch (e) {
      problem =
        e instanceof ApiError && e.status === 403
          ? "That code is not right"
          : e instanceof ApiError && e.status === 409
            ? "Someone already answered this"
            : e instanceof Error
              ? e.message
              : String(e);
    } finally {
      busy = false;
    }
  }

  const AGENT_STATE: Record<HomeOut["agent"]["state"], string> = {
    active: "is active",
    paused: "is paused",
    pairing: "is connecting",
    consent: "waits for you to allow it",
    none: "",
  };
  const WAITS = (n: number) => (n === 0 ? "Nothing needs you right now." : n === 1 ? "One order waits for you." : `${n} orders wait for you.`);

  const steps = (h: HomeOut) => [
    {
      id: "rules",
      done: h.setup.rulesSaved,
      title: "Check your rules",
      detail: "How much your agent orders alone, what needs you, what never goes",
      href: "/rules",
      action: "Rules",
    },
    {
      id: "agent",
      done: h.setup.agentConnected,
      title: "Connect your agent",
      detail: "Add one address to your agent and confirm it with a code",
      href: "/agent",
      action: "Agent",
    },
    {
      id: "order",
      done: h.setup.firstOrder,
      title: "First order via your agent",
      detail: "Ask your agent to order something at Valio, it shows up here",
      href: "/activity",
      action: "Activity",
    },
  ];

  // Until the first order the page is the checklist; the kitchen is set up after it.
  const first = $derived(!!home.data && !home.data.setup.firstOrder);
  const list = $derived(home.data ? steps(home.data) : []);
  const doneCount = $derived(list.filter((s) => s.done).length);
  const next = $derived(list.find((s) => !s.done)?.id);
  // An item in Needs you is not repeated under Latest.
  const latest = $derived.by((): ActivityItem[] => {
    if (!home.data) return [];
    const waiting = new Set(home.data.needsYou.map((i) => i.id));
    return home.data.latest.filter((i) => !waiting.has(i.id));
  });
  const weekPct = $derived(
    home.data?.week.capCents ? Math.round((home.data.week.usedCents / home.data.week.capCents) * 100) : null,
  );

  // Setup finished while the page was open: the one moment Home celebrates (rare, first time).
  let wasFirst: boolean | null = null;
  let celebrate = $state(false);
  // A step that turned done while watching draws its check; one already done just stands.
  const justDone = $state(new Set<string>());
  let doneBefore: Set<string> | null = null;
  $effect(() => {
    if (!home.data) return;
    if (wasFirst === true && !first) celebrate = true;
    wasFirst = first;
    const now = new Set(list.filter((s) => s.done).map((s) => s.id));
    if (doneBefore) for (const id of now) if (!doneBefore.has(id)) justDone.add(id);
    doneBefore = now;
  });

  // Every time Home appears, its parts come in slowly, top to bottom, as one wave (the CSS
  // below). The class stays only for that first wave: rows the agent adds later keep their own
  // arrival (LiveRows), and a poll never replays it.
  let entering = $state(true);
  let waveStarted = false;
  let waveTimer: ReturnType<typeof setTimeout> | undefined;
  $effect(() => {
    if (!home.data || waveStarted) return;
    waveStarted = true;
    waveTimer = setTimeout(() => (entering = false), 1900);
  });
  onDestroy(() => clearTimeout(waveTimer));
</script>

{#snippet lead()}
  <span data-testid="home-lead">Three steps until your agent orders for {session.account?.name}</span>
{/snippet}

<div class="home" class:entering>
<PageHead title="Home" facts={first && session.account ? lead : undefined}>
  {#if home.data && !first}
    {@const h = home.data}
    <p class="lead" data-testid="home-lede">
      {#key WAITS(h.needsYou.length)}<span class="word" class:tone-wait-text={h.needsYou.length > 0} in:blurSwap>{WAITS(h.needsYou.length)}</span>{/key}
      <a class="hit" href="/agent" id="home-agent" data-testid="home-agent">
        {#key h.agent.state}<span in:blurSwap
            >{#if h.agent.state === "none"}No agent connected&nbsp;yet.{:else}{#if h.agent.state === "active"}{#key beat}<span
                    class="beat"
                    class:flash={beat > 0}
                    aria-hidden="true"
                  ></span>{/key}{/if}{h.agent.name ?? "Your agent"} {AGENT_STATE[h.agent.state]}{#if h.agent.state === "active"}{h.agent.lastUsedAt
                  ? `, last call ${ago(h.agent.lastUsedAt, net.now)}`
                  : ", no call yet"}{/if}.{/if}</span
          >{/key}
      </a>
    </p>
  {/if}
</PageHead>

<div class="blocks">
  {#if home.error && !home.data}
    <LoadError detail={home.error} />
  {:else if !home.data}
    <Loading />
  {:else}
    {@const h = home.data}
    {#if first}
      <section class="ls" aria-labelledby="h-setup" data-testid="section-setup">
        <h2 class="v-h" id="h-setup">Get started <em data-testid="setup-count"><Ticker text="{doneCount} of 3" value={doneCount} /></em></h2>
        <ol class="steps">
          {#each list as s, n (s.id)}
            <li class="step" class:done={s.done} class:next={s.id === next} id="step-{s.id}">
              {#if n < list.length - 1}
                <span class="st-link" aria-hidden="true">
                  <Current axis="v" mode={s.done ? (justDone.has(s.id) ? "run" : "lit") : "dim"} />
                </span>
              {/if}
              <span class="st-n num" aria-hidden="true">
                {#if s.done}
                  <svg class="v-check st-check" class:just={justDone.has(s.id)} viewBox="0 0 24 24" width="22" height="22"><path d="M20 6 9 17l-5-5" pathLength="1" /></svg>
                {:else}
                  <span out:fadeOut={{ duration: 120 }}>{n + 1}</span>
                {/if}
              </span>
              <span class="st-main">
                <span class="st-title">{#if s.done}<span class="sr-only">Done: </span>{/if}{s.title}</span>
                {#key s.done}<span class="st-detail" in:blurSwap>{s.done ? "Done" : s.detail}</span>{/key}
              </span>
              <Button
                href={s.href}
                size="sm"
                variant={s.id === next ? "default" : "outline"}
                id="step-{s.id}-go"
                data-testid="step-{s.id}-go">{s.action}</Button
              >
            </li>
          {/each}
        </ol>
      </section>
    {:else}
      {#if celebrate}
        <p class="v-set" data-testid="home-set" in:rise={{ y: 10, duration: 420 }}>
          <svg class="v-check just" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M20 6 9 17l-5-5" pathLength="1" /></svg>
          Your kitchen is set up
        </p>
      {/if}
      <div class="figs" data-testid="home-status">
        <div class="fig wk-fig" data-testid="home-week">
          <span class="f-num num"><Ticker text={nb(money(h.week.usedCents))} value={h.week.usedCents} /></span>
          <span class="f-cap" id="week-label">spent this week{#if h.week.capCents != null}, of <span class="num">{nb(money(h.week.capCents))}</span>{/if}</span>
          {#if weekPct != null}
            <div class="wk" role="progressbar" aria-labelledby="week-label" aria-valuenow={weekPct} aria-valuemin={0} aria-valuemax={100}>
              <span class="wk-fill" style:transform="scaleX({Math.min(100, weekPct) / 100})"></span>
            </div>
          {/if}
        </div>
        <div class="side">
          <div class="fig">
            <span class="f-num sm num" class:wait={h.needsYou.length > 0}><Ticker text={String(h.needsYou.length)} value={h.needsYou.length} /></span>
            <span class="f-cap">waiting for you</span>
          </div>
          {#if alone != null}
            <a class="fig" href="/rules" data-testid="home-alone">
              <span class="f-num sm num">{nb(money(alone))}</span>
              <span class="f-cap">ordered alone, at most</span>
            </a>
          {/if}
        </div>
      </div>
    {/if}

    {#if !first || h.needsYou.length}
      <ListSection id="needs" title="Needs you" count={h.needsYou.length}>
        <LiveRows items={h.needsYou}>
          {#snippet row(i)}
          <div class="need" class:open={approving === i.id} data-testid="need-{i.id}">
            <div class="need-main">
              <span class="need-title">{nb(i.title)}</span>
              <span class="need-why">{nb(i.why)}</span>
            </div>
            <div class="need-end">
              <span class="num need-amt">{nb(total(i.totalCents))}</span>
              {#if approving !== i.id}
                <span class="need-btns" in:fadeOut={{ duration: 120 }}>
                  <Button href="/activity/{encodeURIComponent(i.id)}" size="sm" variant="outline" id="review-{i.id}" data-testid="review-{i.id}"
                    >Review</Button
                  >
                  {#if i.orderId}
                    <Button size="sm" id="approve-{i.id}" data-testid="approve-{i.id}" aria-expanded={false} onclick={() => openApprove(i.id)}>Approve</Button>
                  {/if}
                </span>
              {/if}
            </div>
            {#if approving === i.id}
              <div class="need-code" transition:collapse={{ duration: 220 }}>
                <VCode bind:value={code} error={problem} {busy} submitLabel="Approve" onsubmit={() => approve(i)} oncancel={closeApprove} />
              </div>
            {/if}
          </div>
          {/snippet}
        </LiveRows>
        {#if !h.needsYou.length}
          <p class="none" data-testid="needs-none" in:blurSwap>Nothing waits for you</p>
        {/if}
      </ListSection>
    {/if}

    {#if latest.length}
      <ListSection id="latest" title="Latest" link={{ href: "/activity", label: "All activity" }}>
        <LiveRows items={latest}>{#snippet row(i)}<ActivityRow item={i} />{/snippet}</LiveRows>
      </ListSection>
    {/if}
  {/if}
</div>
</div>

<style>
  .lead a {
    color: var(--v-muted);
    text-decoration-color: var(--v-line-strong);
  }
  @media (hover: hover) and (pointer: fine) {
    .lead a:hover {
      color: var(--valio);
    }
    a.fig:hover .f-cap {
      color: var(--valio);
    }
  }
  .v-set {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 0 0 -16px;
    font-size: var(--fs-body);
    line-height: var(--lh-body);
    font-weight: 500;
    color: var(--v-ok-text);
  }
  .st-n {
    display: inline-grid;
    place-items: center start;
  }
  .st-n > :global(*) {
    grid-area: 1 / 1;
  }
  .ls {
    display: flex;
    flex-direction: column;
  }

  /* Get started: three numbered lines between rules. */
  .steps {
    margin: 0;
    padding: 0;
    list-style: none;
    border-top: 1px solid var(--v-fg);
  }
  .step {
    display: grid;
    grid-template-columns: 32px minmax(0, 1fr) auto;
    column-gap: 16px;
    align-items: center;
    padding: 16px 0;
    border-bottom: 1px solid var(--v-line);
  }
  .st-n {
    font-family: var(--v-sans);
    font-size: 22px;
    line-height: 28px;
    font-weight: 600;
    color: var(--v-faint);
  }
  .step.next .st-n {
    color: var(--valio);
  }
  .step.done .st-n {
    color: var(--v-ok);
  }
  .st-main {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }
  .st-title {
    font-size: var(--fs-body);
    line-height: var(--lh-body);
    font-weight: 500;
  }
  .step.done .st-title {
    color: var(--v-muted);
  }
  .st-detail {
    margin-top: 2px;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-muted);
  }
  .step.done .st-detail {
    color: var(--v-ok-text);
  }

  /* The week: the large figure on the left, what waits and the alone limit on the right. */
  .figs {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: end;
    gap: 24px 48px;
  }
  /* The figure keeps its own width, so the week bar under it stays as wide as the amount. */
  .wk-fig {
    justify-self: start;
  }
  .side {
    display: flex;
    align-items: flex-end;
    gap: 40px;
  }
  .f-num.sm {
    font-size: 24px;
    line-height: 30px;
  }

  /* The agent's beat: a small green mark that swells once in petrol when a call comes in. */
  .beat {
    display: inline-block;
    width: 7px;
    height: 7px;
    margin: 0 8px 0 0;
    border-radius: var(--radius-chip);
    background: var(--v-ok);
    vertical-align: 2px;
  }
  .beat.flash {
    animation: beat var(--v-dur-glow) var(--v-ease-out);
  }
  @keyframes beat {
    from {
      transform: scale(1.7);
      background: var(--valio);
    }
  }

  /* Get started: the steps are joined by the current, lit as far as the kitchen got. */
  .step {
    position: relative;
  }
  .st-link {
    position: absolute;
    left: 6px;
    top: calc(50% + 17px);
    width: 2px;
    height: calc(100% - 34px);
  }
  .fig {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
    color: inherit;
    text-decoration: none;
  }
  a.fig {
    margin: -6px -8px;
    padding: 6px 8px;
    border-radius: var(--radius-button);
    transition: background-color var(--duration-fast) ease;
  }
  a.fig:active {
    background: var(--v-tint-fill);
  }
  .f-num {
    font-family: var(--v-sans);
    font-size: var(--fs-figure);
    line-height: var(--lh-title);
    font-weight: 600;
    letter-spacing: var(--ls-title);
  }
  .f-num.wait {
    color: var(--valio);
  }
  .f-cap {
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-muted);
  }
  /* The week bar: a transform, so it fills on the compositor; it grows in once (plans/009). */
  .wk {
    position: relative;
    width: 100%;
    min-width: 200px;
    height: 4px;
    margin-top: 8px;
    background: var(--v-line);
    overflow: hidden;
  }
  .wk-fill {
    position: absolute;
    inset: 0;
    background: var(--valio);
    transform-origin: left center;
    transition: transform var(--v-dur-moment) var(--v-ease-out);
  }

  /* ---------- Home's entrance: slow, top to bottom, one wave ----------
     Each part fades in while it rises 16 px, over 800 ms on the strong ease-out. The gaps
     shrink as the page goes down (110, 90, 70, 60 ... ms), so it reads as a wave, not a
     metronome. Nothing waits for it: every part is clickable from the first frame. */
  .entering :global(.head h1),
  .entering :global(.head .facts),
  .entering .lead,
  .entering .v-set,
  .entering .fig,
  .entering .step,
  .entering :global(.ls-head),
  .entering :global(.section-card),
  .entering :global(.lr) {
    animation: v-home-in var(--v-dur-wave) var(--v-ease-out) both;
    animation-delay: var(--d, 0ms);
  }
  .entering :global(.section-card) {
    --d: 0ms;
    animation-name: v-home-line;
  }
  .entering :global(.head h1) {
    --d: 0ms;
  }
  .entering :global(.head .facts),
  .entering .lead {
    --d: 110ms;
  }
  .entering .v-set {
    --d: 160ms;
  }
  .entering .step:nth-child(1),
  .entering .fig:nth-child(1) {
    --d: 200ms;
  }
  .entering .step:nth-child(2),
  .entering .fig:nth-child(2) {
    --d: 290ms;
  }
  .entering .step:nth-child(3),
  .entering .fig:nth-child(3) {
    --d: 360ms;
  }
  .entering :global([data-testid="section-needs"] .ls-head) {
    --d: 420ms;
  }
  .entering :global([data-testid="section-needs"] .lr:nth-child(1)) {
    --d: 480ms;
  }
  .entering :global([data-testid="section-needs"] .lr:nth-child(n + 2)) {
    --d: 530ms;
  }
  .entering :global([data-testid="section-latest"] .ls-head) {
    --d: 560ms;
  }
  .entering :global([data-testid="section-latest"] .lr:nth-child(1)) {
    --d: 620ms;
  }
  .entering :global([data-testid="section-latest"] .lr:nth-child(2)) {
    --d: 670ms;
  }
  .entering :global([data-testid="section-latest"] .lr:nth-child(3)) {
    --d: 710ms;
  }
  .entering :global([data-testid="section-latest"] .lr:nth-child(4)) {
    --d: 740ms;
  }
  .entering :global([data-testid="section-latest"] .lr:nth-child(n + 5)) {
    --d: 760ms;
  }
  /* The rule over a list draws from the left instead of rising. */
  .entering :global([data-testid="section-needs"] .section-card) {
    --d: 420ms;
  }
  .entering :global([data-testid="section-latest"] .section-card) {
    --d: 560ms;
  }
  /* The week bar fills from empty once the figure above it has landed. */
  .entering .wk-fill {
    animation: v-wk 1000ms var(--v-ease-out) 450ms backwards;
  }
  @keyframes v-home-in {
    from {
      opacity: 0;
      transform: translateY(16px);
    }
  }
  @keyframes v-home-line {
    from {
      border-top-color: transparent;
    }
  }
  @keyframes v-wk {
    from {
      transform: scaleX(0);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .entering :global(.head h1),
    .entering :global(.head .facts),
    .entering .lead,
    .entering .v-set,
    .entering .fig,
    .entering .step,
    .entering :global(.ls-head),
    .entering :global(.section-card),
    .entering :global(.lr),
    .entering .wk-fill {
      animation: v-fade-in 200ms linear both;
      animation-delay: 0ms;
    }
  }

  .need {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    column-gap: 24px;
    row-gap: 8px;
    min-height: 64px;
    padding: 14px 10px 14px 12px;
    border-left: 2px solid var(--valio);
  }
  .need-main {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }
  .need-title {
    font-size: var(--fs-body);
    line-height: var(--lh-body);
    font-weight: 500;
    overflow-wrap: anywhere;
  }
  .need-why {
    margin-top: 2px;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-muted);
  }
  .need-end {
    display: flex;
    align-items: center;
    gap: 20px;
  }
  .need-btns {
    display: flex;
    gap: 8px;
  }
  .need-code {
    grid-column: 1 / -1;
  }
  .need-amt {
    font-size: var(--fs-body);
    line-height: var(--lh-body);
    white-space: nowrap;
  }
  .none {
    margin: 0;
    padding: 14px 0;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-muted);
  }

  @media (max-width: 760px) {
    .figs {
      grid-template-columns: minmax(0, 1fr);
      gap: 20px;
    }
    .side {
      grid-column: auto;
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
    }
    .st-link {
      display: none;
    }
    .need {
      grid-template-columns: minmax(0, 1fr);
    }
    .need-end {
      justify-content: space-between;
    }
    .step {
      grid-template-columns: 28px minmax(0, 1fr);
      row-gap: 10px;
    }
    .step :global([data-slot="button"]) {
      grid-column: 2;
      justify-self: start;
    }
  }
</style>
