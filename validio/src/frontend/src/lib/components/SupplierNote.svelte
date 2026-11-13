<script lang="ts">
  /// A supplier's own words about a product, shown as what they are: text
  /// nobody checked. A model reads it for tricks aimed at agents; what it found
  /// is shown too, and none of it ever reaches a decision.
  import { Chip } from "@arlen/ui-kit/components/ui/chip";
  import type { SupplierText } from "$lib/api/types";
  import State from "./State.svelte";

  let { text, productId }: { text: SupplierText; productId: string } = $props();

  const FLAG: Record<string, string> = {
    addresses_agents: "Talks to AI agents",
    gives_instruction: "Gives an instruction",
    mentions_claim: "Mentions a claim",
  };
  const flags = $derived(text.reader?.flags ?? []);
</script>

<div class="supplier" data-testid="supplier-{productId}">
  <div class="head">
    <span class="what">Supplier text</span>
    <State label="Untrusted" tone="quiet" id="supplier-{productId}" />
  </div>
  <blockquote>{text.text}</blockquote>
  {#if text.reader && (text.reader.summary || flags.length)}
    <div class="reader" id="reader-{productId}" data-testid="reader-{productId}">
      <p class="by">Read by a model, never used for decisions</p>
      {#if text.reader.summary}<p class="summary">{text.reader.summary}</p>{/if}
      {#if flags.length}
        <ul class="chips" aria-label="What the model found">
          {#each flags as f, i (i)}
            <li><Chip label="{FLAG[f.code] ?? f.code}: {f.text}" /></li>
          {/each}
        </ul>
      {/if}
    </div>
  {/if}
</div>

<style>
  .supplier {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .head {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .what,
  .by {
    margin: 0;
    font-size: var(--text-xs);
    font-weight: 500;
    color: var(--color-fg-secondary);
  }
  blockquote {
    margin: 0;
    padding-inline-start: 0.75rem;
    border-inline-start: 2px solid var(--color-border);
    font-size: var(--text-sm);
    color: var(--color-fg-secondary);
  }
  .reader {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }
  .summary {
    margin: 0;
    font-size: var(--text-sm);
  }
  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .chips li {
    max-width: 100%;
  }
</style>
