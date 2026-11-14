<script lang="ts">
  /// The Options plot: priced options as dots from the cheapest to the
  /// dearest, the chosen one larger and in Valio blue.
  import { money } from "$lib/format";
  import { place, WIDE, type Want } from "./plot";

  let { prices, chosen, said }: { prices: number[]; chosen?: number; said: string } = $props();

  let width = $state(0);
  const lo = $derived(Math.min(...prices));
  const hi = $derived(Math.max(...prices));
  const x = (c: number) => (hi === lo ? width / 2 : 4 + ((width - 8) * (c - lo)) / (hi - lo));
  const narrow = $derived(width > 0 && width < WIDE);

  const labels = $derived.by(() => {
    if (!width || !prices.length) return [];
    const w: Want[] = [];
    if (chosen !== undefined) w.push({ text: `Chosen ${money(chosen)}`, x: x(chosen), align: "center", row: 0, keep: true });
    if (chosen !== lo) w.push({ text: money(lo), x: 0, align: "left", row: 1 });
    if (chosen !== hi && hi !== lo) w.push({ text: money(hi), x: width, align: "right", row: 1 });
    return place(w, width);
  });
</script>

<div class="rc-plot" class:narrow role="img" aria-label={said} bind:clientWidth={width}>
  {#if width && prices.length}
    <svg aria-hidden="true">
      <line x1="0" x2={width} y1="18" y2="18" class="axis" />
      {#each prices as p, i (i)}
        {#if p !== chosen}<circle cx={x(p)} cy="18" r="3" class="dot" />{/if}
      {/each}
      {#if chosen !== undefined}<circle cx={x(chosen)} cy="18" r="4" class="subject" data-plot-subject />{/if}
    </svg>
    {#each labels as l (l.text)}
      <span class="rc-lbl" style:left={l.right === undefined ? `${l.left}px` : undefined} style:right={l.right === undefined ? undefined : `${l.right}px`} style:top="{l.top}px">{l.text}</span>
    {/each}
  {/if}
</div>

<style>
  .axis {
    stroke: var(--v-line);
    stroke-width: 1;
  }
  .dot {
    fill: var(--v-ctx);
  }
  .subject {
    fill: var(--valio);
  }
</style>
