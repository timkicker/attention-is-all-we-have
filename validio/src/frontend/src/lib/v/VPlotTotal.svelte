<script lang="ts">
  /// The Total plot (and the Limits plot on the Spend Pass): an 8 px track
  /// from 0 to 1.1 x the cap, earlier spend in the context grey, this order in
  /// Valio blue, a tick at the auto limit, hatching above the cap.
  import { money } from "$lib/format";
  import { place, WIDE, type Want } from "./plot";

  let {
    before = 0,
    amount,
    auto,
    cap,
    pass = false,
  }: { before?: number; amount: number; auto?: number; cap?: number; pass?: boolean } = $props();

  let width = $state(0);
  const max = $derived(Math.max(1.1 * (cap ?? auto ?? before + amount), before + amount, 1));
  const x = (c: number) => (width * c) / max;
  const end = $derived(x(before + amount));
  const tickX = $derived(auto === undefined ? undefined : x(auto));
  const tall = $derived(tickX !== undefined && Math.abs(tickX - end) <= 4);
  const narrow = $derived(width > 0 && width < WIDE);
  const id = `h${Math.random().toString(36).slice(2, 8)}`;

  const labels = $derived.by(() => {
    if (!width) return [];
    const w: Want[] = [];
    if (cap !== undefined)
      w.push({ text: `${money(cap)} never above`, x: x(cap), align: "right", row: 1, keep: true, testid: pass ? "pass-cap" : undefined });
    if (auto !== undefined)
      w.push({ text: `${money(auto)} alone`, x: x(auto), align: narrow ? "left" : "center", row: 0, testid: pass ? "pass-auto" : undefined });
    return place(w, width);
  });

  const said = $derived(
    [
      pass ? `${money(amount)} used` : before ? `${money(before)} ordered before, this order ${money(amount)}` : `This order ${money(amount)}`,
      auto !== undefined ? `orders alone up to ${money(auto)}` : "",
      cap !== undefined ? `never above ${money(cap)}` : "",
    ]
      .filter(Boolean)
      .join(", ") + ".",
  );
</script>

<div class="rc-plot" class:narrow role="img" aria-label={said} bind:clientWidth={width}>
  {#if width}
    <svg aria-hidden="true">
      <defs>
        <clipPath id="{id}-c"><rect x="0" y="14" width={width} height="8" rx="4" /></clipPath>
        <pattern id="{id}-p" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <line x1="0" y1="0" x2="0" y2="6" class="hatch" />
        </pattern>
      </defs>
      <g clip-path="url(#{id}-c)">
        <rect x="0" y="14" width={width} height="8" class="track" />
        {#if pass && auto !== undefined && cap !== undefined}
          <rect x={x(auto)} y="14" width={x(cap) - x(auto)} height="8" class="asks" />
        {/if}
        {#if cap !== undefined}
          <rect x={x(cap)} y="14" width={width - x(cap)} height="8" fill="url(#{id}-p)" />
        {/if}
        {#if before > 0}
          <rect x="0" y="14" width={x(before)} height="8" class="before" />
        {/if}
        {#if amount > 0}
          <rect x={x(before)} y="14" width={Math.max(0, x(before + amount) - x(before))} height="8" class="subject" data-plot-subject />
        {/if}
      </g>
      {#if tickX !== undefined}
        {#if tall}
          <rect x={tickX - 1} y="10" width="2" height="16" class="tick-tall" />
        {:else}
          <rect x={tickX - 1} y="12" width="2" height="12" class="tick" />
        {/if}
      {/if}
    </svg>
    {#each labels as l (l.text)}
      <span class="rc-lbl" style:left={l.right === undefined ? `${l.left}px` : undefined} style:right={l.right === undefined ? undefined : `${l.right}px`} style:top="{l.top}px" data-testid={l.testid} id={l.testid}>{l.text}</span>
    {/each}
  {/if}
</div>

<style>
  .track {
    fill: color-mix(in srgb, var(--v-fg) 6%, transparent);
  }
  .asks {
    fill: color-mix(in srgb, var(--v-fg) 10%, transparent);
  }
  .hatch {
    stroke: color-mix(in srgb, var(--v-fg) 14%, transparent);
    stroke-width: 2;
  }
  .before {
    fill: var(--v-ctx);
  }
  .subject {
    fill: var(--valio);
  }
  .tick {
    fill: var(--v-ctx);
  }
  .tick-tall {
    fill: var(--v-fg);
  }
</style>
