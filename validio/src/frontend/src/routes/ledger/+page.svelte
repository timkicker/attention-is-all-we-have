<script lang="ts">
  // The open ledger, one line per entry as Arlen's knowledge rows read: what
  // kind of thing happened, what it was in one sentence, who did it, when.
  // Whether the chain holds comes first. The recorded text, rules, shown Spend
  // Pass fields and hashes open under an entry.
  import * as Collapsible from "@arlen/ui-kit/components/ui/collapsible";
  import {
    CalendarSync,
    CircleCheck,
    FileText,
    FlaskConical,
    Scale,
    ShieldCheck,
    ShieldX,
    ShoppingCart,
  } from "@lucide/svelte";
  import { api } from "$lib/api/client";
  import type { LedgerEntry } from "$lib/api/types";
  import { setChrome } from "$lib/chrome.svelte";
  import { sentences, time } from "$lib/format";
  import { live } from "$lib/live.svelte";
  import Facts from "$lib/components/Facts.svelte";
  import Info from "$lib/components/Info.svelte";
  import State from "$lib/components/State.svelte";

  setChrome("Open ledger");
  const ledger = live(() => api.ledger());

  const entries = $derived([...(ledger.data?.entries ?? [])].reverse());

  const KIND: Record<string, { label: string; icon: typeof FileText }> = {
    request: { label: "Request", icon: FileText },
    decision: { label: "Decision", icon: Scale },
    order: { label: "Order", icon: ShoppingCart },
    approval: { label: "Approval", icon: CircleCheck },
    simulation: { label: "Simulated", icon: FlaskConical },
    renewal: { label: "Renewal", icon: CalendarSync },
  };
  const who = (actor: string) => {
    const [kind, name] = actor.split(":");
    if (kind === "agent") return "Agent";
    if (kind === "validio") return "Validio";
    if (kind === "kitchen" && name) return name.charAt(0).toUpperCase() + name.slice(1);
    return actor.charAt(0).toUpperCase() + actor.slice(1);
  };
  const short = (h: string) => (h.length > 16 ? `${h.slice(0, 8)}…${h.slice(-6)}` : h);
  const people = $derived(entries.filter((e) => e.kind === "approval").length);
  const orders = $derived(entries.filter((e) => e.kind === "order").length);
</script>

<div class="ledger-page">
  {#if ledger.data}
    {@const chain = ledger.data.chain}
    <header class="head">
      <h2 class="chain" id="chain-status" data-testid="chain-status" class:bad={!chain.ok}>
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
        <span class="sr-only">over {chain.count} entries</span>
      </h2>
      <Facts
        items={[
          { value: String(chain.count), label: "entries" },
          { value: String(orders), label: "orders" },
          { value: String(people), label: "decided by a person" },
        ]}
      />
    </header>

    <ol class="rows" id="ledger" data-testid="ledger">
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
  {@const k = KIND[e.kind] ?? { label: e.kind, icon: FileText }}
  {@const said = sentences(e.sentence)}
  <li class="entry" id="entry-{e.seq}" data-testid="ledger-entry">
    <Collapsible.Root>
      <Collapsible.Trigger class="line">
        <span class="icon" aria-hidden="true"><k.icon size={15} strokeWidth={1.75} /></span>
        <span class="object">{said[0] ?? ""}</span>
        <span class="who">{who(e.actor)}</span>
        <span class="when num">{time(e.at)}</span>
        <Collapsible.Chevron />
      </Collapsible.Trigger>
      <Collapsible.Content forceMount>
        {#snippet child({ props, open })}
          <div {...props} hidden={!open} class="more" id="entry-more-{e.seq}">
            {#if said.length > 1}<p class="rest">{said.slice(1).join(" ")}</p>{/if}
            <dl>
              <dt>Kind</dt>
              <dd><State label={k.label} tone="quiet" /></dd>
              <dt>Entry</dt>
              <dd class="num">#{e.seq}{#if e.orderId}, order {e.orderId}{/if}</dd>
              <dt>Actor</dt>
              <dd class="mono">{e.actor}</dd>
              {#if e.ruleIds.length}<dt>Rules</dt><dd class="mono">{e.ruleIds.join(", ")}</dd>{/if}
              {#if e.disclosed.length}<dt>Spend Pass fields shown</dt><dd class="mono">{e.disclosed.join(", ")}</dd>{/if}
              <dt>As recorded</dt>
              <dd class="recorded" data-raw>{e.sentence}</dd>
              <dt>Hash</dt>
              <dd class="mono">{short(e.hash)}</dd>
              <dt>Previous</dt>
              <dd class="mono">{short(e.prevHash)}</dd>
            </dl>
          </div>
        {/snippet}
      </Collapsible.Content>
    </Collapsible.Root>
  </li>
{/snippet}

<style>
  .ledger-page {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
    max-width: 60rem;
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
  .chain.bad :global(svg:first-child) {
    color: var(--destructive-on-tint);
  }
  .rows {
    display: flex;
    flex-direction: column;
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .entry {
    border-bottom: 1px solid color-mix(in srgb, var(--foreground) 6%, transparent);
  }
  .rows :global(.line) {
    display: grid;
    grid-template-columns: 1.25rem minmax(0, 1fr) 5.5rem 5.5rem 1rem;
    gap: 0.75rem;
    align-items: baseline;
    width: 100%;
    padding: 0.5rem 0.35rem;
    border-radius: var(--radius-input);
    text-align: start;
    cursor: pointer;
  }
  .rows :global(.line:hover) {
    background: color-mix(in srgb, var(--color-fg-primary) 5%, transparent);
  }
  .icon {
    display: inline-flex;
    align-self: center;
    color: var(--color-fg-secondary);
  }
  .object {
    min-width: 0;
    font-size: var(--text-sm);
    line-height: 1.45;
  }
  .who {
    font-size: var(--text-xs);
    color: var(--color-fg-secondary);
  }
  .when {
    text-align: end;
    font-size: var(--text-xs);
    color: var(--color-fg-secondary);
  }
  .rows :global(.kit-chevron) {
    align-self: center;
    color: var(--color-fg-secondary);
  }
  .more {
    margin: 0 0 0.75rem 2rem;
    padding: 0.6rem 0.75rem;
    border-radius: var(--radius-input);
    background: color-mix(in srgb, var(--color-fg-primary) 4%, transparent);
    font-size: var(--text-xs);
  }
  .rest {
    margin: 0 0 0.6rem;
    max-width: 70ch;
    font-size: var(--text-sm);
  }
  dl {
    display: grid;
    grid-template-columns: max-content minmax(0, 1fr);
    gap: 0.3rem 1rem;
    margin: 0;
  }
  dt {
    color: var(--color-fg-secondary);
  }
  dd {
    margin: 0;
    overflow-wrap: anywhere;
  }
  .recorded {
    color: var(--color-fg-secondary);
  }
  .empty {
    padding: 1rem 0;
    font-size: var(--text-sm);
  }
  @media (max-width: 760px) {
    .ledger-page {
      padding: 1rem 1rem 2rem;
    }
    .rows :global(.line) {
      grid-template-columns: 1.25rem minmax(0, 1fr) 1rem;
      gap: 0.15rem 0.6rem;
    }
    .who,
    .when {
      grid-column: 2;
      text-align: start;
      font-size: var(--text-2xs);
    }
    .when {
      grid-row: 3;
    }
    .rows :global(.kit-chevron) {
      grid-column: 3;
      grid-row: 1;
    }
    .more {
      margin-inline-start: 0;
    }
  }
</style>
