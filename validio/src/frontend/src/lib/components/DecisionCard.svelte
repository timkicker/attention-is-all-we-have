<script lang="ts">
  // The answer first: what happened, in the sentence the ledger keeps.
  import { Badge } from "@arlen/ui-kit/components/ui/badge";
  import type { SupplyRequest } from "$lib/api/types";
  import { money } from "$lib/format";
  import StatusBadge from "./StatusBadge.svelte";
  import type { Snippet } from "svelte";

  let { request, action }: { request: SupplyRequest; action?: Snippet } = $props();
</script>

<section class="decision" id="decision" data-status={request.status} aria-label="Decision">
  <div class="top">
    <StatusBadge status={request.status} />
    {#each request.decision.ruleIds as rule (rule)}
      <Badge variant="outline">rule {rule}</Badge>
    {/each}
    <span class="live num" id="live-checked">Checked {request.liveChecked} products live</span>
  </div>
  <p class="sentence" id="decision-sentence">
    {request.status === "waiting" && request.question ? request.question : request.decision.sentence}
  </p>
  <div class="foot">
    {#if request.totalCents !== undefined}
      <span class="total num">{money(request.totalCents)}</span>
    {/if}
    {#if action}<div class="action">{@render action()}</div>{/if}
  </div>
</section>

<style>
  .decision {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    padding: 1.25rem 1.25rem 1rem;
    border-radius: var(--radius-card);
    border: 1px solid color-mix(in srgb, var(--foreground) 10%, transparent);
    background: var(--card);
    box-shadow: var(--shadow-card, none);
  }
  .decision[data-status="waiting"] {
    border-color: color-mix(in srgb, var(--color-warning) 55%, transparent);
  }
  .decision[data-status="ordered_alone"],
  .decision[data-status="ordered"] {
    border-color: color-mix(in srgb, var(--color-success) 45%, transparent);
  }
  .top {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
  }
  .live {
    margin-inline-start: auto;
    font-size: var(--text-xs);
    color: color-mix(in srgb, var(--foreground) 64%, transparent);
  }
  .sentence {
    margin: 0;
    font-size: var(--text-lg);
    line-height: 1.4;
    font-weight: 500;
    color: var(--foreground);
    max-width: 60ch;
    text-wrap: pretty;
  }
  .foot {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
  }
  .total {
    font-size: var(--text-xl);
    font-weight: 600;
  }
</style>
