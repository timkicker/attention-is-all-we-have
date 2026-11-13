<script lang="ts">
  /// Eight weeks of one line as bars, oldest left. The usual amount is a line
  /// across, so the drift shows as bars climbing over it.
  let { history, usual, unit, id }: { history: number[]; usual?: number; unit: string; id?: string } = $props();

  const top = $derived(Math.max(...history, usual ?? 0) * 1.1 || 1);
  const pct = (n: number) => (n / top) * 100;
  const label = $derived(
    `${unit} per week over ${history.length} weeks, oldest first: ${history.join(", ")}` +
      (usual !== undefined ? `. Usual ${usual}.` : "."),
  );
</script>

<figure class="drift" {id}>
  <div class="plot" role="img" aria-label={label}>
    {#if usual !== undefined}
      <span class="usual" style="bottom: {pct(usual)}%"><span class="usual-l num">usual {usual}</span></span>
    {/if}
    {#each history as n, i (i)}
      <span class="bar" class:recent={i >= history.length - 2} style="height: {pct(n)}%">
        <span class="v num">{n}</span>
      </span>
    {/each}
  </div>
  <figcaption class="axis">
    <span>{history.length} weeks ago</span>
    <span>last week</span>
  </figcaption>
</figure>

<style>
  .drift {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    max-width: 26rem;
    margin: 0;
    padding-inline-end: 4.5rem;
  }
  .plot {
    position: relative;
    display: flex;
    align-items: flex-end;
    gap: 0.35rem;
    height: 5.5rem;
    padding-top: 1rem;
    border-bottom: 1px solid var(--color-border);
  }
  .bar {
    position: relative;
    flex: 1;
    border-radius: 2px 2px 0 0;
    background: color-mix(in srgb, var(--color-fg-primary) 22%, transparent);
  }
  .bar.recent {
    background: var(--color-fg-primary);
  }
  .v {
    position: absolute;
    bottom: 100%;
    left: 50%;
    translate: -50% -0.1rem;
    font-size: var(--text-2xs);
    color: var(--color-fg-secondary);
  }
  .usual {
    position: absolute;
    left: 0;
    right: 0;
    z-index: 1;
    border-top: 1px dashed var(--color-fg-secondary);
  }
  .usual-l {
    position: absolute;
    left: 100%;
    top: -0.5rem;
    padding-inline-start: 0.4rem;
    white-space: nowrap;
    font-size: var(--text-2xs);
    color: var(--color-fg-secondary);
  }
  .axis {
    display: flex;
    margin-inline-end: 0;
    justify-content: space-between;
    font-size: var(--text-2xs);
    color: var(--color-fg-secondary);
  }
</style>
