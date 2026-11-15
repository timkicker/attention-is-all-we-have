<script lang="ts">
  /// What Validio does, drawn once on the door (plans/014): your agent asks, Validio checks with
  /// Valio, then orders alone, asks you, or blocks. A small packet runs the path, one outcome per
  /// round, calmly and with a long pause; it stops while the tab is hidden and never moves under
  /// reduced motion (then every outcome stands lit).
  import { onMount } from "svelte";
  import { reduced } from "$lib/motion";

  const OUT = [
    { y: 27, label: "Ordered alone" },
    { y: 75, label: "Waits for you" },
    { y: 123, label: "Blocked" },
  ];
  const EASE_MOVE = "cubic-bezier(0.77, 0, 0.175, 1)";
  const EASE_OUT = "cubic-bezier(0.23, 1, 0.32, 1)";

  let packet = $state<SVGRectElement>();
  let ring = $state<SVGRectElement>();
  let lit = $state(-1);
  let still = $state(false);

  onMount(() => {
    if (reduced()) {
      still = true;
      return;
    }
    let alive = true;
    const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
    const at = (x: number, y: number) => ({ transform: `translate(${x}px, ${y}px)` });
    (async () => {
      await sleep(800);
      let n = 0;
      while (alive) {
        if (document.visibilityState === "hidden" || !packet || !ring) {
          await sleep(500);
          continue;
        }
        const k = n++ % 3;
        packet.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 150, fill: "forwards" });
        await packet.animate([at(92, 75), at(172, 75)], { duration: 600, easing: EASE_MOVE, fill: "forwards" }).finished;
        await ring.animate([{ transform: "scale(1)", opacity: 0.5 }, { transform: "scale(1.35, 1.8)", opacity: 0 }], { duration: 400, easing: EASE_OUT }).finished;
        lit = k;
        await packet.animate([at(252, 75), at(300, OUT[k].y)], { duration: 500, easing: EASE_MOVE, fill: "forwards" }).finished;
        packet.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 200, fill: "forwards" });
        await sleep(1200);
        lit = -1;
        await sleep(1600);
      }
    })().catch(() => {});
    return () => (alive = false);
  });
</script>

<svg class="flow" class:still viewBox="0 0 440 150" role="img" aria-label="Your agent asks Validio. Validio checks Valio, then orders alone, asks you, or blocks.">
  <g class="node">
    <rect x="0.5" y="63.5" width="92" height="24" rx="3" />
    <text x="46.5" y="79.5">Your agent</text>
  </g>
  <line class="path" x1="92.5" y1="75.5" x2="172.5" y2="75.5" />
  <g class="node v">
    <rect class="ring" bind:this={ring} x="172.5" y="63.5" width="80" height="24" rx="3" />
    <rect x="172.5" y="63.5" width="80" height="24" rx="3" />
    <text x="212.5" y="79.5">Validio</text>
  </g>
  {#each OUT as o, i (o.label)}
    <line class="path" x1="252.5" y1="75.5" x2="300.5" y2={o.y + 0.5} />
    <text class="out" class:lit={still || lit === i} x="310" y={o.y + 4.5}>{o.label}</text>
  {/each}
  <rect class="packet" bind:this={packet} x="-3" y="-3" width="6" height="6" rx="1.5" />
</svg>

<style>
  .flow {
    display: block;
    width: 100%;
    max-width: 520px;
    height: auto;
    overflow: visible;
  }
  .path {
    stroke: var(--valio-band-muted);
    stroke-width: 1.25;
    opacity: 0.6;
  }
  .node rect {
    fill: none;
    stroke: var(--valio-band-muted);
    stroke-width: 1;
  }
  .node.v rect:not(.ring) {
    stroke: var(--valio-band-fg);
  }
  .ring {
    transform-box: fill-box;
    transform-origin: center;
    opacity: 0;
  }
  text {
    fill: var(--valio-band-fg);
    font-family: var(--v-sans);
    font-size: 12.5px;
    text-anchor: middle;
  }
  .out {
    text-anchor: start;
    fill: var(--valio-band-muted);
    transition: fill var(--v-dur-ui) var(--v-ease-out);
  }
  .out.lit {
    fill: var(--valio-band-fg);
  }
  .packet {
    fill: var(--valio-band-fg);
    opacity: 0;
  }
</style>
