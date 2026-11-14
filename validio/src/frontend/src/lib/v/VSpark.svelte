<script lang="ts">
  /// halbat's spark: thin weekly bars on a baseline, the current weeks in the
  /// foreground. The scale starts at 80 % of the smallest week, so a rise shows.
  /// The usual amount is text next to it, not a line through the bars.
  let { values, usual, unit }: { values: number[]; usual: number; unit: string } = $props();
  const BAR = 4;
  const GAP = 3;
  const H = 24;
  const lo = $derived(0.8 * Math.min(...values));
  const hi = $derived(Math.max(...values));
  const h = (v: number) => (hi - lo > 0 ? Math.max(2, (H * (v - lo)) / (hi - lo)) : H / 2);
  const w = $derived(values.length * (BAR + GAP) - GAP);
  const said = $derived(`${values.length} weeks: ${values.join(", ")} ${unit}. Usual ${usual}.`);
</script>

<span class="spark-wrap">
  <svg class="spark" width={w} height={H} viewBox="0 0 {w} {H}" role="img" aria-label={said}>
    {#each values as v, i (i)}
      <rect x={i * (BAR + GAP)} y={H - h(v)} width={BAR} height={h(v)} rx="1" class:now={i >= values.length - 2} />
    {/each}
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
  .spark {
    flex: none;
  }
  rect {
    fill: var(--v-ctx);
  }
  rect.now {
    fill: var(--v-fg);
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
    white-space: nowrap;
  }
</style>
