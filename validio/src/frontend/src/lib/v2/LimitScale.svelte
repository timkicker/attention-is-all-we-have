<script lang="ts">
  /// The Rules as a picture (plans/010): ordered alone, waiting for you, blocked, as three zones on
  /// one 8 px scale. `edit` adds two grips that drag 1:1 and answer the arrow keys; `order` adds a
  /// marker that travels once to where this order landed.
  ///
  /// Everything is placed with transforms in percent of a full-width layer, so nothing is measured
  /// except the track's box on the first touch of a drag.
  import { money } from "$lib/format";

  type Which = "alone" | "waiting";
  let {
    alone,
    waiting,
    order = null,
    mode = "read",
    onchange,
    id,
  }: {
    alone: number;
    waiting: number;
    order?: number | null;
    mode?: "read" | "edit" | "order";
    onchange?: (v: { alone: number; waiting: number }) => void;
    id?: string;
  } = $props();

  const MAX_CENTS = 10_000_000;
  const STEP = 5000; // 50 €
  const BIG = 50000; // 500 €
  let dragging = $state<Which | null>(null);
  let instant = $state(false);
  // While dragging, the scale holds still; otherwise the grip would run from the pointer.
  let frozen = $state<number | null>(null);
  // How far past the other grip the pointer went, shown at a fifth (friction, not a wall).
  let over = $state(0);

  const span = $derived(frozen ?? Math.max(waiting * 1.25, (order ?? 0) * 1.06, 10000));
  const pct = (c: number) => Math.max(0, Math.min(100, (c / span) * 100));
  const a = $derived(pct(alone));
  const w = $derived(pct(waiting));
  const visual = (which: Which) => (which === "alone" ? a : w) + (dragging === which ? over : 0);

  let track = $state<HTMLElement>();
  let box = { left: 0, width: 1 };
  // The track's width: marks are moved in pixels, on the compositor, and never stick out of it.
  let tw = $state(0);
  let ready = $state(false);
  $effect(() => {
    if (tw > 0 && !ready) requestAnimationFrame(() => requestAnimationFrame(() => (ready = true)));
  });
  const px = (p: number) => `translateX(${(p / 100) * tw}px)`;

  function set(which: Which, cents: number) {
    let al = alone;
    let wt = waiting;
    if (which === "alone") al = Math.max(0, Math.min(cents, wt));
    else wt = Math.min(MAX_CENTS, Math.max(cents, al));
    if (al !== alone || wt !== waiting) onchange?.({ alone: al, waiting: wt });
  }

  function down(e: PointerEvent, which: Which) {
    if (!track) return;
    e.preventDefault();
    const r = track.getBoundingClientRect();
    box = { left: r.left, width: Math.max(1, r.width) };
    frozen = span;
    dragging = which;
    over = 0;
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    (e.currentTarget as HTMLElement).focus();
  }
  function move(e: PointerEvent) {
    if (!dragging || frozen === null) return;
    const raw = Math.round(((e.clientX - box.left) / box.width) * frozen);
    const cents = Math.round(raw / 1000) * 1000; // 10 € while dragging
    const lo = dragging === "waiting" ? alone : 0;
    const hi = dragging === "alone" ? waiting : MAX_CENTS;
    const past = cents > hi ? cents - hi : cents < lo ? cents - lo : 0;
    over = (past / frozen) * 100 * 0.2;
    set(dragging, cents);
  }
  function up() {
    if (!dragging) return;
    const which = dragging;
    dragging = null;
    over = 0;
    frozen = null;
    const v = which === "alone" ? alone : waiting;
    set(which, Math.round(v / STEP) * STEP); // settles on a 50 € step, with the transition
  }
  function key(e: KeyboardEvent, which: Which) {
    const v = which === "alone" ? alone : waiting;
    const step = e.shiftKey ? BIG : STEP;
    let next: number | null = null;
    if (e.key === "ArrowRight" || e.key === "ArrowUp") next = v + step;
    else if (e.key === "ArrowLeft" || e.key === "ArrowDown") next = v - step;
    else if (e.key === "Home") next = which === "alone" ? 0 : alone;
    else if (e.key === "End") next = which === "alone" ? waiting : MAX_CENTS;
    if (next === null) return;
    e.preventDefault();
    // Keyboard moves are instant: no animation on a keyboard action.
    instant = true;
    set(which, next);
    requestAnimationFrame(() => requestAnimationFrame(() => (instant = false)));
  }

  const summary = $derived(
    `Ordered alone up to ${money(alone)}. Waiting for you up to ${money(waiting)}. Blocked above.` +
      (order != null ? ` This order ${money(order)}.` : ""),
  );
  const LABEL: Record<Which, string> = { alone: "Ordered alone", waiting: "Waiting for you" };
  const GRIPS: Which[] = ["alone", "waiting"];
</script>

<div class="lsc" class:dragging={!!dragging} class:instant class:ready {id} data-testid={id}>
  <div
    class="track"
    bind:this={track}
    bind:clientWidth={tw}
    role={mode === "edit" ? "group" : "img"}
    aria-label={mode === "edit" ? "Limits" : summary}
    style:--a={visual("alone")}
    style:--w={visual("waiting")}
  >
    <span class="zone ok"></span>
    <span class="zone wait"></span>
    <span class="zone bad"></span>
    <span class="edge" style:transform={px(visual("alone"))}></span>
    <span class="edge" style:transform={px(visual("waiting"))}></span>
    {#if mode === "order" && order != null && tw > 0}
      <span class="mk" style:--x="{(pct(order) / 100) * tw}px" aria-hidden="true"></span>
    {/if}
    {#if mode === "edit"}
      {#each GRIPS as which (which)}
        <span class="hd" style:transform={px(visual(which))}>
          <button
            type="button"
            class="grip"
            class:on={dragging === which}
            role="slider"
            id="{id}-{which}"
            data-testid="{id}-{which}"
            aria-label={LABEL[which]}
            aria-valuemin={which === "alone" ? 0 : alone}
            aria-valuemax={which === "alone" ? waiting : MAX_CENTS}
            aria-valuenow={which === "alone" ? alone : waiting}
            aria-valuetext={money(which === "alone" ? alone : waiting)}
            onpointerdown={(e) => down(e, which)}
            onpointermove={move}
            onpointerup={up}
            onpointercancel={up}
            onkeydown={(e) => key(e, which)}
          ><span class="bar" aria-hidden="true"></span></button>
        </span>
      {/each}
    {/if}
  </div>
  <ul class="legend num" aria-hidden={mode !== "edit" ? "true" : undefined}>
    {#if mode === "order" && order != null}<li class="l-order"><i></i>This order {money(order)}</li>{/if}
    <!-- The read view's rows say the amounts; the legend there only names the zones. -->
    <li class="l-ok"><i></i>{mode === "read" ? "Ordered alone" : `Alone up to ${money(alone)}`}</li>
    <li class="l-wait"><i></i>{mode === "read" ? "Waiting for you" : `Waits up to ${money(waiting)}`}</li>
    <li class="l-bad"><i></i>Blocked above</li>
  </ul>
</div>

<style>
  .lsc {
    display: flex;
    flex-direction: column;
    gap: 10px;
    min-width: 0;
  }
  .track {
    position: relative;
    height: 8px;
    margin: 12px 0 4px;
  }
  .zone {
    position: absolute;
    inset: 0;
  }
  /* Zero-width marks at the left edge, moved in pixels. */
  .edge,
  .mk,
  .hd {
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 0;
  }
  .zone {
    transition: clip-path var(--v-dur-ui) var(--v-ease-in-out);
  }
  .zone.ok {
    background: var(--v-wash-ok);
    clip-path: inset(0 calc(100% - var(--a) * 1%) 0 0);
  }
  .zone.wait {
    background: var(--v-wash-wait);
    clip-path: inset(0 calc(100% - var(--w) * 1%) 0 calc(var(--a) * 1%));
  }
  .zone.bad {
    background: var(--v-wash-bad);
    clip-path: inset(0 0 0 calc(var(--w) * 1%));
  }
  /* A layer the width of the track, moved by its own width in percent: the line sits at p %. */
  .edge,
  .hd {
    pointer-events: none;
  }
  .ready .edge,
  .ready .hd {
    transition: transform var(--v-dur-ui) var(--v-ease-in-out);
  }
  .edge::before {
    content: "";
    position: absolute;
    left: -0.5px;
    top: -3px;
    bottom: -3px;
    width: 1px;
    background: var(--v-fg);
  }
  .mk {
    pointer-events: none;
    transform: translateX(var(--x));
    transition:
      transform var(--v-dur-moment) var(--v-ease-out),
      opacity var(--v-dur-ui) var(--v-ease-out);
  }
  .mk::before {
    content: "";
    position: absolute;
    left: -1px;
    top: -6px;
    bottom: -6px;
    width: 2px;
    background: var(--valio);
  }
  @starting-style {
    .mk {
      transform: translateX(0px);
      opacity: 0;
    }
  }
  .dragging .zone,
  .dragging .edge,
  .dragging .hd,
  .instant .zone,
  .instant .edge,
  .instant .hd {
    transition: none;
  }
  .grip {
    position: absolute;
    left: -12px;
    top: -12px;
    width: 24px;
    height: 32px;
    display: grid;
    place-items: center;
    padding: 0;
    border: 0;
    background: none;
    cursor: ew-resize;
    pointer-events: auto;
    touch-action: none;
  }
  .grip .bar {
    width: 4px;
    height: 20px;
    border-radius: var(--radius-chip);
    background: var(--v-fg);
    transition: transform var(--v-dur-press) var(--v-ease-out);
  }
  .grip.on .bar,
  .grip:active .bar {
    transform: scaleY(1.15);
  }
  @media (hover: hover) and (pointer: fine) {
    .grip:hover .bar {
      background: var(--valio);
    }
  }
  .grip:focus-visible {
    outline-offset: 0;
    border-radius: var(--radius-chip);
  }
  .legend {
    display: flex;
    flex-wrap: wrap;
    gap: 6px 20px;
    margin: 0;
    padding: 0;
    list-style: none;
    font-size: var(--fs-cap);
    line-height: 16px;
    color: var(--v-muted);
  }
  .legend li {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    white-space: nowrap;
  }
  .legend i {
    width: 10px;
    height: 10px;
    border-radius: var(--radius-chip);
  }
  .l-ok i {
    background: var(--v-wash-ok);
    box-shadow: inset 0 0 0 1px var(--v-ok);
  }
  .l-wait i {
    background: var(--v-wash-wait);
    box-shadow: inset 0 0 0 1px var(--valio);
  }
  .l-bad i {
    background: var(--v-wash-bad);
    box-shadow: inset 0 0 0 1px var(--v-bad);
  }
  .l-order i {
    width: 2px;
    height: 12px;
    border-radius: 0;
    background: var(--valio);
  }
  .l-order {
    color: var(--v-fg);
    font-weight: 500;
  }
  @media (prefers-reduced-motion: reduce) {
    .zone,
    .edge,
    .hd {
      transition: none;
    }
    @starting-style {
      .mk {
        transform: translateX(var(--x));
      }
    }
  }
  @media (max-width: 760px) {
    .grip {
      left: -22px;
      top: -18px;
      width: 44px;
      height: 44px;
    }
  }
</style>
