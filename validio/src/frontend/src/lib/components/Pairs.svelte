<script lang="ts" module>
  export type Pair = { label: string; value: string; note?: string; id?: string; quiet?: boolean };
</script>

<script lang="ts">
  /// Label and value right next to each other, the way a record reads: a
  /// muted label column, the value straight after it, a hairline between rows.
  /// Below 760px the label sits above its value, so no word ever splits.
  let { items, id }: { items: Pair[]; id?: string } = $props();
</script>

<dl class="pairs" {id}>
  {#each items as p (p.label)}
    <div class="pair" id={p.id} data-testid={p.id}>
      <dt>{p.label}</dt>
      <dd class:quiet={p.quiet}>{p.value}{#if p.note}<span class="note"> {p.note}</span>{/if}</dd>
    </div>
  {/each}
</dl>

<style>
  .pairs {
    display: flex;
    flex-direction: column;
    margin: 0;
  }
  .pair {
    display: grid;
    grid-template-columns: 12rem minmax(0, 1fr);
    gap: 1rem;
    padding-block: 0.5rem;
    font-size: var(--text-sm);
  }
  .pair + .pair {
    border-top: 1px solid color-mix(in srgb, var(--foreground) 7%, transparent);
  }
  dt {
    color: var(--color-fg-secondary);
  }
  dd {
    margin: 0;
    font-weight: 500;
    overflow-wrap: normal;
  }
  dd.quiet {
    font-weight: 400;
    color: var(--color-fg-secondary);
  }
  .note {
    font-size: var(--text-xs);
    font-weight: 400;
    color: var(--color-fg-secondary);
  }
  @media (max-width: 760px) {
    .pair {
      grid-template-columns: 1fr;
      gap: 0.1rem;
      padding-block: 0.6rem;
    }
    dt {
      font-size: var(--text-xs);
    }
    dd {
      font-size: var(--text-md, var(--text-sm));
    }
  }
</style>
