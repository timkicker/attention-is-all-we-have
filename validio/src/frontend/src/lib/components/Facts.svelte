<script lang="ts">
  /// The line of figures under a title, halbat's facts line: the value strong,
  /// its label quiet, wide gaps, no separators.
  let { items, id }: { items: { value: string; label: string; before?: boolean }[]; id?: string } = $props();
</script>

<p class="facts" {id}>
  {#each items as f (f.label)}
    <span class="fact">
      {#if f.before}<span class="l">{f.label}</span> <span class="v num">{f.value}</span>
      {:else}<span class="v num">{f.value}</span> <span class="l">{f.label}</span>{/if}
    </span>
  {/each}
</p>

<style>
  .facts {
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem 1.5rem;
    margin: 0;
    font-size: var(--text-sm);
  }
  .v {
    color: var(--color-fg-primary);
    font-weight: 500;
  }
  .l {
    color: var(--color-fg-secondary);
  }
</style>
