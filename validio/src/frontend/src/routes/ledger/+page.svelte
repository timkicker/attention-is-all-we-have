<script lang="ts">
  // The open ledger as a timeline: whether the chain holds comes first, then
  // every entry in one sentence, newest on top. The hashes, rules and shown
  // Spend Pass fields of an entry open under it.
  import { ShieldCheck, ShieldX, ChevronRight } from "@lucide/svelte";
  import { api } from "$lib/api/client";
  import type { LedgerEntry } from "$lib/api/types";
  import { setChrome } from "$lib/chrome.svelte";
  import { time } from "$lib/format";
  import { live } from "$lib/live.svelte";
  import Facts from "$lib/components/Facts.svelte";
  import Info from "$lib/components/Info.svelte";
  import State from "$lib/components/State.svelte";

  setChrome("Open ledger");
  const ledger = live(() => api.ledger());

  const entries = $derived([...(ledger.data?.entries ?? [])].reverse());
  let open = $state<Record<number, boolean>>({});

  const KIND: Record<string, string> = {
    request: "Request",
    decision: "Decision",
    order: "Order",
    approval: "Approval",
    simulation: "Simulated",
    renewal: "Renewal",
  };
  const who = (actor: string) => {
    const [kind, name] = actor.split(":");
    if (!name) return actor === "validio" ? "Validio" : actor.charAt(0).toUpperCase() + actor.slice(1);
    if (kind === "agent") return "Agent";
    if (kind === "kitchen") return name.charAt(0).toUpperCase() + name.slice(1);
    if (kind === "validio") return "Validio";
    return actor;
  };
  const short = (h: string) => (h.length > 16 ? `${h.slice(0, 8)}…${h.slice(-6)}` : h);
  const people = $derived(entries.filter((e) => e.kind === "approval").length);
  const orders = $derived(entries.filter((e) => e.kind === "order").length);
</script>

<div class="ledger-page">
  {#if ledger.data}
    {@const chain = ledger.data.chain}
    <header class="head">
      <p class="chain" id="chain-status" class:bad={!chain.ok}>
        {#if chain.ok}
          <ShieldCheck size={18} strokeWidth={1.75} aria-hidden="true" />
          Chain verified
        {:else}
          <ShieldX size={18} strokeWidth={1.75} aria-hidden="true" />
          Chain broken at entry {chain.brokenAt}
        {/if}
        <Info
          label="What the chain proves"
          text="Each entry carries the hash of the one before it. Change one letter anywhere and every later hash stops matching, so the ledger shows where."
        />
      </p>
      <Facts
        items={[
          { value: String(chain.count), label: "entries" },
          { value: String(orders), label: "orders" },
          { value: String(people), label: "decided by a person" },
        ]}
      />
    </header>

    <ol class="timeline" id="ledger">
      {#each entries as e (e.seq)}
        {@render entry(e)}
      {:else}
        <li class="empty t-quiet">Nothing happened yet.</li>
      {/each}
    </ol>
  {:else if ledger.error}
    <p class="t-quiet">Cannot read the ledger: {ledger.error}</p>
  {/if}
</div>

{#snippet entry(e: LedgerEntry)}
  <li class="entry" id="entry-{e.seq}">
    <span class="when num">{time(e.at).slice(0, 5)}</span>
    <span class="mark" aria-hidden="true"></span>
    <div class="body">
      <button
        type="button"
        class="line"
        aria-expanded={!!open[e.seq]}
        aria-controls="entry-more-{e.seq}"
        onclick={() => (open[e.seq] = !open[e.seq])}
      >
        <span class="who">{who(e.actor)}</span>
        <span class="sentence">{e.sentence}</span>
        <span class="chev" class:on={open[e.seq]}><ChevronRight size={14} strokeWidth={2} /></span>
      </button>
      <div class="tags">
        <State label={KIND[e.kind] ?? e.kind} tone="quiet" />
        {#if e.orderId}<span class="mono t-quiet">{e.orderId}</span>{/if}
        <span class="mono t-quiet">#{e.seq}</span>
      </div>
      {#if open[e.seq]}
        <dl class="more" id="entry-more-{e.seq}">
          <dt>Actor</dt>
          <dd class="mono">{e.actor}</dd>
          {#if e.ruleIds.length}<dt>Rules</dt><dd class="mono">{e.ruleIds.join(", ")}</dd>{/if}
          {#if e.disclosed.length}<dt>Spend Pass fields shown</dt><dd class="mono">{e.disclosed.join(", ")}</dd>{/if}
          <dt>Hash</dt>
          <dd class="mono" title={e.hash}>{short(e.hash)}</dd>
          <dt>Previous</dt>
          <dd class="mono" title={e.prevHash}>{short(e.prevHash)}</dd>
        </dl>
      {/if}
    </div>
  </li>
{/snippet}

<style>
  .ledger-page {
    display: flex;
    flex-direction: column;
    gap: 1.75rem;
    max-width: 52rem;
    padding: 1.5rem 1.75rem 3rem;
  }
  .head {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .chain {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin: 0;
    font-size: var(--text-lg);
    font-weight: 600;
  }
  .chain :global(svg) {
    color: color-mix(in srgb, var(--color-success) 76%, var(--foreground));
  }
  .chain.bad :global(svg) {
    color: var(--destructive-on-tint);
  }
  .timeline {
    position: relative;
    display: flex;
    flex-direction: column;
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .entry {
    display: grid;
    grid-template-columns: 3rem 1rem minmax(0, 1fr);
    gap: 0 0.5rem;
  }
  .when {
    padding-top: 0.55rem;
    text-align: end;
    font-size: var(--text-2xs);
    color: var(--color-fg-secondary);
  }
  .mark {
    position: relative;
  }
  .mark::before {
    content: "";
    position: absolute;
    inset-block: 0;
    left: 50%;
    width: 1px;
    background: var(--color-border);
  }
  .mark::after {
    content: "";
    position: absolute;
    top: 0.85rem;
    left: 50%;
    width: 0.45rem;
    height: 0.45rem;
    margin-left: -0.225rem;
    border-radius: 50%;
    background: var(--color-bg-app);
    border: 1px solid var(--color-fg-secondary);
  }
  .entry:first-child .mark::before {
    top: 0.85rem;
  }
  .entry:last-child .mark::before {
    bottom: calc(100% - 0.85rem);
  }
  .body {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
    padding: 0.4rem 0 0.9rem;
    min-width: 0;
  }
  .line {
    display: grid;
    grid-template-columns: 4.5rem minmax(0, 1fr) auto;
    gap: 0.75rem;
    align-items: start;
    padding: 0.15rem 0.35rem;
    margin-inline: -0.35rem;
    border-radius: var(--radius-input);
    text-align: start;
    font: inherit;
    color: inherit;
    background: none;
    border: 0;
    cursor: pointer;
  }
  .line:hover {
    background: color-mix(in srgb, var(--color-fg-primary) 5%, transparent);
  }
  .who {
    text-align: end;
    font-size: var(--text-xs);
    padding-top: 0.1rem;
    color: var(--color-fg-secondary);
  }
  .sentence {
    max-width: 64ch;
    font-size: var(--text-sm);
    line-height: 1.5;
  }
  .chev {
    display: inline-flex;
    padding-top: 0.2rem;
    color: var(--color-fg-secondary);
    transition: rotate var(--duration-normal) var(--ease-out);
  }
  .chev.on {
    rotate: 90deg;
  }
  .tags {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding-inline-start: 5.25rem;
    font-size: var(--text-2xs);
  }
  .more {
    display: grid;
    grid-template-columns: max-content minmax(0, 1fr);
    gap: 0.25rem 1rem;
    margin: 0.4rem 0 0 5.25rem;
    padding: 0.6rem 0.75rem;
    border-radius: var(--radius-input);
    background: color-mix(in srgb, var(--color-fg-primary) 4%, transparent);
    font-size: var(--text-xs);
  }
  dt {
    color: var(--color-fg-secondary);
  }
  dd {
    margin: 0;
    overflow-wrap: anywhere;
  }
  .empty {
    padding: 1rem 0;
    font-size: var(--text-sm);
  }
  @media (prefers-reduced-motion: reduce) {
    .chev {
      transition: none;
    }
  }
  @media (max-width: 760px) {
    .ledger-page {
      padding: 1rem 1rem 2rem;
    }
    .entry {
      grid-template-columns: 0.75rem minmax(0, 1fr);
    }
    .when {
      display: none;
    }
    .line {
      grid-template-columns: minmax(0, 1fr) auto;
    }
    .who {
      grid-column: 1 / -1;
      text-align: start;
    }
    .tags,
    .more {
      padding-inline-start: 0;
      margin-inline-start: 0;
    }
  }
</style>
