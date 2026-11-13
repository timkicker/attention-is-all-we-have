<script lang="ts">
  // One ledger entry: the sentence first, the facts and the chain fold out.
  import { Badge } from "@arlen/ui-kit/components/ui/badge";
  import * as Collapsible from "@arlen/ui-kit/components/ui/collapsible";
  import type { LedgerEntry } from "$lib/api/types";
  import { FIELD, time } from "$lib/format";
  import FactList from "./FactList.svelte";

  let { entry, broken = false }: { entry: LedgerEntry; broken?: boolean } = $props();
  const KIND = { request: "Request", decision: "Decision", order: "Order", approval: "Approval", simulation: "Simulated", renewal: "Renewal" };
</script>

<div class="entry" class:broken id="entry-{entry.seq}">
  <span class="seq num">{entry.seq}</span>
  <div class="body">
    <div class="head">
      <Badge variant={entry.kind === "simulation" ? "warn" : "outline"}>{KIND[entry.kind]}</Badge>
      <span class="who">{entry.actor}</span>
      <span class="when num">{time(entry.at)}</span>
    </div>
    <p class="sentence">{entry.sentence}</p>
    <Collapsible.Root>
      <Collapsible.Trigger class="facts-toggle" id="entry-{entry.seq}-details">
        <Collapsible.Chevron size={13} />
        Details
      </Collapsible.Trigger>
      <Collapsible.Content>
        <div class="details">
          <FactList facts={entry.facts} />
          <dl class="meta">
            {#if entry.spendPassId}<div><dt>Spend Pass</dt><dd>{entry.spendPassId}</dd></div>{/if}
            {#if entry.disclosed.length}<div><dt>Shown fields</dt><dd>{entry.disclosed.map((k) => FIELD[k] ?? k).join(", ")}</dd></div>{/if}
            {#if entry.ruleIds.length}<div><dt>Rules</dt><dd>{entry.ruleIds.join(", ")}</dd></div>{/if}
            {#if entry.orderId}<div><dt>Order</dt><dd>{entry.orderId}</dd></div>{/if}
            <div><dt>Hash before</dt><dd class="hash">{entry.prevHash}</dd></div>
            <div><dt>Hash</dt><dd class="hash">{entry.hash}</dd></div>
          </dl>
        </div>
      </Collapsible.Content>
    </Collapsible.Root>
  </div>
</div>

<style>
  .entry {
    display: grid;
    grid-template-columns: 1.75rem 1fr;
    gap: 0.75rem;
    padding: var(--space-row, 0.75rem) 1rem;
  }
  .entry.broken {
    background: color-mix(in srgb, var(--color-error) 7%, transparent);
  }
  .seq {
    font-size: var(--text-sm);
    font-weight: 600;
    color: color-mix(in srgb, var(--foreground) 55%, transparent);
    line-height: 1.6;
  }
  .body {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
    min-width: 0;
  }
  .head {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
    font-size: var(--text-xs);
    color: color-mix(in srgb, var(--foreground) 64%, transparent);
  }
  .when {
    margin-inline-start: auto;
  }
  .sentence {
    margin: 0;
    font-size: var(--text-sm);
    line-height: 1.5;
    max-width: 68ch;
  }
  .details {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    padding-block: 0.25rem;
  }
  .meta {
    display: grid;
    gap: 0.25rem;
    margin: 0;
    font-size: var(--text-xs);
  }
  .meta div {
    display: grid;
    grid-template-columns: 9rem 1fr;
    gap: 0.75rem;
  }
  dt {
    color: color-mix(in srgb, var(--foreground) 64%, transparent);
  }
  dd {
    margin: 0;
    min-width: 0;
  }
  .hash {
    font-family: ui-monospace, monospace;
    font-size: var(--text-2xs);
    overflow-wrap: anywhere;
  }
  @media (max-width: 480px) {
    .meta div {
      grid-template-columns: 1fr;
      gap: 0;
    }
  }
</style>
