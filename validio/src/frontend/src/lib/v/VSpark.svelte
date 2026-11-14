<script lang="ts">
  /// halbat's spark: 8 weekly bars, the last two in the foreground, a line at the usual amount.
  let { values, usual, unit }: { values: number[]; usual: number; unit: string } = $props();
  const max = $derived(Math.max(...values, usual) || 1);
  const h = (v: number) => Math.max(2, (24 * v) / max);
  const said = $derived(`${values.length} weeks: ${values.join(", ")} ${unit}. Usual ${usual}.`);
</script>

<span class="spark-wrap">
  <svg class="spark" width="110" height="24" viewBox="0 0 110 24" preserveAspectRatio="none" role="img" aria-label={said}>
    {#each values as v, i (i)}
      <rect x={i * 14} y={24 - h(v)} width="10" height={h(v)} class:now={i >= values.length - 2} />
    {/each}
    <line x1="0" x2="110" y1={24 - h(usual) + 0.5} y2={24 - h(usual) + 0.5} class="base" vector-effect="non-scaling-stroke" />
  </svg>
  <span class="spark-n" aria-hidden="true">
    <b>{values[values.length - 1]}</b>
    <small>usual {usual}</small>
  </span>
</span>

<style>
  .spark-wrap {
    display: inline-flex;
    align-items: center;
    gap: 12px;
  }
  rect {
    fill: var(--v-ctx);
  }
  rect.now {
    fill: var(--v-fg);
  }
  .base {
    stroke: var(--v-muted);
    stroke-width: 1;
  }
  .spark-n {
    display: flex;
    flex-direction: column;
    text-align: right;
    font-variant-numeric: tabular-nums;
  }
  .spark-n b {
    font-size: var(--fs-body);
    line-height: 22px;
    font-weight: 600;
  }
  .spark-n small {
    font-size: var(--fs-cap);
    line-height: 16px;
    color: var(--v-muted);
  }
  @media (max-width: 760px) {
    .spark-wrap {
      display: flex;
      width: 100%;
    }
    .spark {
      flex: 1;
      height: 32px;
    }
  }
</style>
