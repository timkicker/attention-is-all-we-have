<script lang="ts">
  /// Home: what needs the owner now and what ran last. Until the first order
  /// came through the agent it is a three step checklist; after that one line
  /// with the agent and the week, Needs you, and the newest rows. Live: the
  /// page asks again every two seconds, so an order the agent places shows up
  /// without a reload.
  import { Circle, CircleCheck } from "@lucide/svelte";
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import { Progress } from "@arlen/ui-kit/components/ui/progress";
  import { Row } from "@arlen/ui-kit/components/ui/row";
  import { Section } from "@arlen/ui-kit/components/ui/section";
  import { api } from "$lib/api/client";
  import type { ActivityItem, HomeOut } from "$lib/api/types";
  import { session } from "$lib/owner.svelte";
  import { ActivityRow, ListSection, live, Loading, LoadError, money, nb, PageHead, total } from "$lib/v2";

  const home = live(() => api.home());

  const AGENT_STATE: Record<HomeOut["agent"]["state"], string> = {
    active: "active",
    paused: "paused",
    pairing: "connecting",
    consent: "waits for you to allow it",
    none: "",
  };

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

<PageHead title="Home" facts={first && session.account ? lead : undefined} />

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
        <Section class="v-card">
          {#each list as s (s.id)}
            <Row id="step-{s.id}" label={s.title} description={s.detail}>
              {#snippet leading()}
                {#if s.done}
                  <CircleCheck class="step-done" size={18} strokeWidth={1.75} aria-hidden="true" />
                  <span class="sr-only">Done:</span>
                {:else}
                  <Circle class="step-open" size={18} strokeWidth={1.75} aria-hidden="true" />
                {/if}
              {/snippet}
              {#snippet control()}
                <Button
                  href={s.href}
                  size="sm"
                  variant={s.id === next ? "default" : "outline"}
                  id="step-{s.id}-go"
                  data-testid="step-{s.id}-go">{s.action}</Button
                >
              {/snippet}
            </Row>
          {/each}
        </Section>
      </section>
    {:else}
      <Section class="v-card">
        <div class="status" data-testid="home-status">
          <a class="st-agent hit" href="/agent" id="home-agent" data-testid="home-agent">
            <span class="dot" class:on={h.agent.state === "active"} aria-hidden="true"></span>
            {#if h.agent.state === "none"}
              <span>No agent connected</span>
            {:else}
              <span class="st-name">{h.agent.name ?? "Your agent"}</span>
              <span class="muted">{AGENT_STATE[h.agent.state]}</span>
            {/if}
          </a>
          <div class="st-week" data-testid="home-week">
            <span id="week-label">
              <span class="muted">This week</span>
              <b class="num">{nb(money(h.week.usedCents))}</b>
              {#if h.week.capCents != null}<span class="muted">of</span> <span class="num">{nb(money(h.week.capCents))}</span>{/if}
            </span>
            {#if weekPct != null}<Progress value={weekPct} labelledby="week-label" />{/if}
          </div>
        </div>
      </Section>
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
  .ls {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .ls .v-h {
    margin: 0;
  }
  .ls :global(.step-done) {
    color: var(--v-ok-text);
  }
  .ls :global(.step-open) {
    color: var(--v-faint);
  }

  .status {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(240px, 320px);
    align-items: center;
    column-gap: 24px;
    padding: 12px 16px;
  }
  .st-agent {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    justify-self: start;
    min-height: 32px;
    font-size: var(--fs-body);
    line-height: var(--lh-body);
    color: inherit;
    text-decoration: none;
  }
  .st-agent:hover .st-name,
  .st-agent:hover > span:last-child {
    text-decoration: underline;
    text-decoration-color: var(--v-faint);
    text-underline-offset: 3px;
  }
  .st-name {
    font-weight: 500;
  }
  .dot {
    width: 8px;
    height: 8px;
    flex: none;
    border-radius: var(--radius-chip);
    background: var(--v-faint);
  }
  .dot.on {
    background: var(--v-ok);
  }
  .st-week {
    display: flex;
    flex-direction: column;
    gap: 8px;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
  }
  .st-week b {
    font-weight: 500;
  }

  .need {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    column-gap: 16px;
    row-gap: 8px;
    min-height: 64px;
    padding: 12px 16px;
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
    gap: 16px;
  }
  .need-amt {
    font-size: var(--fs-body);
    line-height: var(--lh-body);
    font-weight: 500;
    white-space: nowrap;
  }
  .none {
    margin: 0;
    padding: 12px 16px;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-muted);
  }

  @media (max-width: 760px) {
    .status {
      grid-template-columns: minmax(0, 1fr);
      row-gap: 8px;
    }
    .need {
      grid-template-columns: minmax(0, 1fr);
    }
    .need-end {
      justify-content: space-between;
    }
  }
</style>
