<script lang="ts">
  // Amount per week as small bars, so the drift is visible at a glance. The
  // weeks Drift Watch compares are marked: the first four against the last two.
  let { weeks, unit, label }: { weeks: number[]; unit: string; label: string } = $props();
  const max = $derived(Math.max(...weeks));
  const H = 56;
</script>

<figure class="bars" aria-label={label}>
  <div class="plot" style="height: {H}px">
    {#each weeks as w, i (i)}
      <div class="col" class:base={i < 4} class:recent={i >= weeks.length - 2}>
        <span class="val num">{w}</span>
        <span class="bar" style="height: {Math.round((w / max) * (H - 16))}px"></span>
      </div>
    {/each}
  </div>
  <figcaption>{unit} per week, 8 weeks. First 4 against the last 2.</figcaption>
</figure>

<style>
  .bars {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
    margin: 0;
  }
  .plot {
    display: flex;
    align-items: flex-end;
    gap: 0.25rem;
  }
  .col {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: flex-end;
    gap: 0.125rem;
    width: 1.75rem;
  }
  .val {
    font-size: var(--text-2xs);
    color: color-mix(in srgb, var(--foreground) 64%, transparent);
  }
  .bar {
    width: 100%;
    border-radius: var(--radius-sm) var(--radius-sm) 0 0;
    background: color-mix(in srgb, var(--foreground) 16%, transparent);
  }
  .base .bar {
    background: color-mix(in srgb, var(--foreground) 32%, transparent);
  }
  .recent .bar {
    background: var(--color-warning);
  }
  .recent .val {
    color: var(--foreground);
    font-weight: 600;
  }
  figcaption {
    font-size: var(--text-2xs);
    color: color-mix(in srgb, var(--foreground) 64%, transparent);
  }
</style>
