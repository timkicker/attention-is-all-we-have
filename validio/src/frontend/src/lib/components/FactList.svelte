<script lang="ts">
  // The facts behind one option: field, value and how far it can be trusted.
  import type { Fact } from "$lib/api/types";
  import GradeBadge from "./GradeBadge.svelte";

  let { facts }: { facts: Fact[] } = $props();

  const show = (v: Fact["value"]) => (v === true ? "yes" : v === false ? "no" : v === null ? "none" : String(v));
</script>

{#if facts.length}
  <dl class="facts">
    {#each facts as fact (fact.field + fact.source)}
      <div class="fact">
        <dt>{fact.field}</dt>
        <dd>
          <span class="value">{show(fact.value)}{fact.note ? `, ${fact.note}` : ""}</span>
          <GradeBadge {fact} />
        </dd>
      </div>
    {/each}
  </dl>
{/if}

<style>
  .facts {
    display: grid;
    gap: 0.25rem;
    margin: 0;
  }
  .fact {
    display: grid;
    grid-template-columns: 9rem 1fr;
    gap: 0.75rem;
    align-items: baseline;
    font-size: var(--text-xs);
  }
  dt {
    color: color-mix(in srgb, var(--foreground) 64%, transparent);
  }
  dd {
    margin: 0;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
    color: var(--foreground);
  }
  @media (max-width: 480px) {
    .fact {
      grid-template-columns: 1fr;
      gap: 0.125rem;
    }
  }
</style>
