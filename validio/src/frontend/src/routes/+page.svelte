<script lang="ts">
  /// Home: what needs the owner now and what ran last. Until the first order
  /// came through the agent it is a three step checklist; after that a lede
  /// sentence (what waits, how the agent is), the week's figures, Needs you,
  /// and the newest rows. Live: the page asks again every two seconds, so an
  /// order the agent places shows up without a reload.
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import { Progress } from "@arlen/ui-kit/components/ui/progress";
  import { agentApi } from "$lib/api/agent";
  import { api } from "$lib/api/client";
  import type { ActivityItem, HomeOut } from "$lib/api/types";
  import { session } from "$lib/owner.svelte";
  import { ActivityRow, ListSection, live, Loading, LoadError, money, nb, PageHead, total } from "$lib/v2";

  const home = live(() => api.home());

  // The most the agent orders alone, for the figures; only once the rules were saved.
  const rules = live(() => agentApi.rules().catch(() => null));
  const alone = $derived(rules.data?.saved ? rules.data.aloneUpToCents : null);

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
</script>

{#snippet lead()}
  <span data-testid="home-lead">Three steps until your agent orders for {session.account?.name}</span>
{/snippet}

<PageHead title="Home" facts={first && session.account ? lead : undefined}>
  {#if home.data && !first}
    {@const h = home.data}
    <p class="lead" data-testid="home-lede">
      <span class="word" class:tone-wait-text={h.needsYou.length > 0}>{WAITS(h.needsYou.length)}</span>
      <a class="hit" href="/agent" id="home-agent" data-testid="home-agent">
        {#if h.agent.state === "none"}No agent connected yet.{:else}{h.agent.name ?? "Your agent"} {AGENT_STATE[h.agent.state]}.{/if}
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
        <h2 class="v-h" id="h-setup">Get started <em data-testid="setup-count">{doneCount} of 3</em></h2>
        <ol class="steps">
          {#each list as s, n (s.id)}
            <li class="step" class:done={s.done} class:next={s.id === next} id="step-{s.id}">
              <span class="st-n num" aria-hidden="true">{n + 1}</span>
              <span class="st-main">
                <span class="st-title">{#if s.done}<span class="sr-only">Done: </span>{/if}{s.title}</span>
                <span class="st-detail">{s.done ? "Done" : s.detail}</span>
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
      <div class="figs" data-testid="home-status">
        <div class="fig" data-testid="home-week">
          <span class="f-num num">{nb(money(h.week.usedCents))}</span>
          <span class="f-cap" id="week-label">spent this week{#if h.week.capCents != null}, of <span class="num">{nb(money(h.week.capCents))}</span>{/if}</span>
          {#if weekPct != null}<Progress value={weekPct} labelledby="week-label" />{/if}
        </div>
        <div class="fig">
          <span class="f-num num" class:wait={h.needsYou.length > 0}>{h.needsYou.length}</span>
          <span class="f-cap">waiting for you</span>
        </div>
        {#if alone != null}
          <a class="fig end" href="/rules" data-testid="home-alone">
            <span class="f-num num">{nb(money(alone))}</span>
            <span class="f-cap">ordered alone, at most</span>
          </a>
        {/if}
      </div>
    {/if}

    {#if !first || h.needsYou.length}
      <ListSection id="needs" title="Needs you" count={h.needsYou.length}>
        {#each h.needsYou as i (i.id)}
          <div class="need" data-testid="need-{i.id}">
            <div class="need-main">
              <span class="need-title">{nb(i.title)}</span>
              <span class="need-why">{nb(i.why)}</span>
            </div>
            <div class="need-end">
              <span class="num need-amt">{nb(total(i.totalCents))}</span>
              <Button href="/activity/{encodeURIComponent(i.id)}" size="sm" id="review-{i.id}" data-testid="review-{i.id}"
                >Review</Button
              >
            </div>
          </div>
        {:else}
          <p class="none" data-testid="needs-none">Nothing waits for you</p>
        {/each}
      </ListSection>
    {/if}

    {#if latest.length}
      <ListSection id="latest" title="Latest" link={{ href: "/activity", label: "All activity" }}>
        {#each latest as i (i.id)}<ActivityRow item={i} />{/each}
      </ListSection>
    {/if}
  {/if}
</div>

<style>
  .lead a {
    color: var(--v-muted);
    text-decoration-color: var(--v-line-strong);
  }
  .lead a:hover {
    color: var(--valio);
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

  /* The week in large figures, no boxes. */
  .figs {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-start;
    gap: 24px 64px;
  }
  .fig {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
    color: inherit;
    text-decoration: none;
  }
  .fig.end {
    margin-left: auto;
    text-align: right;
  }
  a.fig:hover .f-cap {
    color: var(--valio);
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
  .fig :global(.progress) {
    width: 100%;
    min-width: 200px;
    height: 4px;
    margin-top: 8px;
    border-radius: 0;
    background: var(--v-line);
  }
  .fig :global(.progress-fill) {
    border-radius: 0;
    background: var(--valio);
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
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 20px 16px;
    }
    .fig:first-child {
      grid-column: 1 / -1;
    }
    .fig.end {
      margin-left: 0;
      text-align: left;
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
