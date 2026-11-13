<script lang="ts">
  // The open ledger, one line per entry: when, what happened in one sentence,
  // who. Whether the chain holds comes first. The raw record, rules, shown
  // Spend Pass fields and hashes open under an entry; nothing is open at first.
  import * as Collapsible from "@arlen/ui-kit/components/ui/collapsible";
  import { api } from "$lib/api/client";
  import type { LedgerEntry } from "$lib/api/types";
  import { setChrome } from "$lib/chrome.svelte";
  import { hm, holderWord, prose, sentences, time } from "$lib/format";
  import { live } from "$lib/live.svelte";
  import Frame from "$lib/components/Frame.svelte";
  import Info from "$lib/components/Info.svelte";

  setChrome("Ledger");
  const ledger = live(() => api.ledger());

  const newest = $derived([...(ledger.data?.entries ?? [])].reverse());

  const KIND: Record<string, { label: string }> = {
    request: { label: "Request" },
    decision: { label: "Decision" },
    order: { label: "Order" },
    approval: { label: "Approval" },
    simulation: { label: "Simulated" },
    renewal: { label: "Renewal" },
  };
  // Backend keys in words; an unknown key is split into words, never shown raw.
  const FIELD: Record<string, string> = {
    autoLimitCents: "auto limit",
    hardCapCents: "hard cap",
    diet: "diet",
    deliverBy: "delivery date",
    categories: "product groups",
    substitutes: "substitutes",
    split: "splitting",
    preferLabels: "preferred labels",
  };
  const fieldKey = (k: string) => FIELD[k] ?? k.replace(/Cents$/, "").replace(/([a-z])([A-Z])/g, "$1 $2").toLowerCase();
  const ruleWord = (r: string) => r.replaceAll("-", " ").replaceAll("_", " ");

  const short = (h: string) => (h.length > 16 ? `${h.slice(0, 8)}…${h.slice(-6)}` : h);
</script>

<Frame title="Ledger" top>
  {#snippet head()}
    {#if ledger.data}
      {@const chain = ledger.data.chain}
      <p class="facts">
        <span class="chain" id="chain-status" data-testid="chain-status" class:bad={!chain.ok}>
          {#if chain.ok}Chain verified · <span class="num">{chain.count}</span> entries{:else}Chain broken at entry {chain.brokenAt} of {chain.count}{/if}
        </span>
        <Info
          label="What the chain proves"
          text="Each entry carries the hash of the one before it. Change one letter anywhere and every later hash stops matching, so the ledger shows where."
        />
      </p>
    {/if}
  {/snippet}
  {#if ledger.data}
    <ol class="rows" id="ledger" data-testid="ledger">
      {#each newest as e (e.seq)}
        {@render entry(e)}
      {:else}
        <li class="empty t-quiet">Nothing happened yet.</li>
      {/each}
    </ol>
  {:else if ledger.error}
    <p class="t-quiet">Cannot read the ledger: {ledger.error}</p>
  {/if}
</Frame>

{#snippet entry(e: LedgerEntry)}
  {@const k = KIND[e.kind] ?? { label: e.kind }}
  {@const said = sentences(e.sentence)}
  <li class="entry" id="entry-{e.seq}" data-testid="ledger-entry">
    <Collapsible.Root>
      <Collapsible.Trigger class="line">
        <span class="when num">{hm(e.at)}</span>
        <span class="object">{prose(said[0] ?? "")}</span>
        <span class="who">{holderWord(e.actor)}</span>
        <Collapsible.Chevron />
      </Collapsible.Trigger>
      <Collapsible.Content forceMount>
        {#snippet child({ props, open })}
          <div {...props} hidden={!open} class="more" id="entry-more-{e.seq}">
            {#if said.length > 1}<p class="rest">{said.slice(1).join(" ")}</p>{/if}
            <dl>
              <dt>Entry</dt>
              <dd class="num">#{e.seq}, {k.label.toLowerCase()}{#if e.orderId}, order {e.orderId}{/if}, {time(e.at)}</dd>
              {#if e.ruleIds.length}<dt>Rules</dt><dd>{e.ruleIds.map(ruleWord).join(", ")}</dd>{/if}
              {#if e.disclosed.length}<dt>Spend Pass fields shown</dt><dd>{e.disclosed.map(fieldKey).join(", ")}</dd>{/if}
              <dt>Raw record</dt>
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
  .facts {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    margin: 0;
    font-size: var(--text-sm);
  }
  .chain {
    font-weight: 500;
  }
  .chain.bad {
    color: var(--destructive-on-tint);
  }
  .rows {
    display: flex;
    flex-direction: column;
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .entry + .entry {
    border-top: 1px solid color-mix(in srgb, var(--foreground) 7%, transparent);
  }
  .rows :global(.line) {
    display: grid;
    grid-template-columns: 3.5rem minmax(0, 1fr) 6rem 1rem;
    gap: 0.75rem;
    align-items: baseline;
    width: 100%;
    padding: 0.5rem 0.35rem;
    border-radius: var(--radius-input);
    text-align: start;
  }
  .rows :global(.line:hover) {
    background: color-mix(in srgb, var(--color-fg-primary) 5%, transparent);
  }
  .when,
  .who {
    font-size: var(--text-xs);
    color: var(--color-fg-secondary);
  }
  .object {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: var(--text-sm);
  }
  .rows :global(.kit-chevron) {
    align-self: center;
  }
  .more {
    margin: 0 0 0.75rem calc(3.5rem + 1.1rem);
    padding: 0.25rem 0;
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
    overflow-wrap: break-word;
  }
  .recorded {
    color: var(--color-fg-secondary);
  }
  .empty {
    padding: 1rem 0;
    font-size: var(--text-sm);
  }
  @media (max-width: 760px) {
    /* Two lines: the event, then "Validio · 10:00". */
    .rows :global(.line) {
      grid-template-columns: auto auto minmax(0, 1fr) 1rem;
      gap: 0.15rem 0.35rem;
    }
    .object {
      grid-column: 1 / 4;
      grid-row: 1;
      white-space: normal;
    }
    .who {
      grid-column: 1;
      grid-row: 2;
    }
    .who::after {
      content: " ·";
    }
    .when {
      grid-column: 2;
      grid-row: 2;
    }
    .rows :global(.kit-chevron) {
      grid-column: 4;
      grid-row: 1;
    }
    .more {
      margin-inline-start: 0;
    }
  }
</style>
