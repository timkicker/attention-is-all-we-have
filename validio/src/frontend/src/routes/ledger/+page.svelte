<script lang="ts">
  import { Page } from "@arlen/ui-kit/components/ui/page";
  import { Section } from "@arlen/ui-kit/components/ui/section";
  import { Notice } from "@arlen/ui-kit/components/ui/notice";
  import { ShieldCheck, ShieldAlert } from "@lucide/svelte";
  import { api } from "$lib/api/client";
  import type { Ledger } from "$lib/api/types";
  import LedgerLine from "$lib/components/LedgerLine.svelte";
  import { poll } from "$lib/poll";

  let ledger = $state<Ledger | null>(null);
  let error = $state("");

  $effect(() =>
    poll(async () => {
      try {
        ledger = await api.ledger();
        error = "";
      } catch (e) {
        error = `The ledger could not be loaded: ${(e as Error).message}`;
      }
    }),
  );
</script>

<Page title="Open Ledger" description="Every decision as one sentence with its facts. The kitchen and Valio read this same view.">
  {#if error}<Notice tone="error" text={error} />{/if}
  {#if ledger}
    <div class="stack">
      <Section label="Entries" id="ledger">
        {#each ledger.entries as entry (entry.seq)}
          <LedgerLine {entry} broken={ledger.chain.brokenAt !== undefined && entry.seq >= ledger.chain.brokenAt} />
        {/each}
      </Section>
      <div class="chain" class:bad={!ledger.chain.ok} id="chain-status" role="status">
        {#if ledger.chain.ok}
          <ShieldCheck size={18} strokeWidth={2} aria-hidden="true" />
          <span><strong>Chain verified</strong>, {ledger.chain.count} entries. Each hash was recomputed from the first entry on.</span>
        {:else}
          <ShieldAlert size={18} strokeWidth={2} aria-hidden="true" />
          <span><strong>Chain broken at entry {ledger.chain.brokenAt}</strong>. That entry or one before it was changed after it was written.</span>
        {/if}
      </div>
    </div>
  {/if}
</Page>

<style>
  .stack {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    width: 100%;
    max-width: var(--width-section-body, 46rem);
    margin-inline: auto;
  }
  .chain {
    display: flex;
    align-items: flex-start;
    gap: 0.625rem;
    padding: 0.875rem 1rem;
    border-radius: var(--radius-card);
    border: 1px solid color-mix(in srgb, var(--color-success) 45%, transparent);
    background: color-mix(in srgb, var(--color-success) 7%, var(--card));
    font-size: var(--text-sm);
    line-height: 1.45;
  }
  .chain :global(svg) {
    flex-shrink: 0;
    color: color-mix(in srgb, var(--color-success) 80%, var(--foreground));
  }
  .chain.bad {
    border-color: color-mix(in srgb, var(--color-error) 45%, transparent);
    background: color-mix(in srgb, var(--color-error) 7%, var(--card));
  }
  .chain.bad :global(svg) {
    color: var(--color-error);
  }
</style>
