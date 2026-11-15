<script lang="ts">
  /// The current (plans/025): one thin line that carries a decision, with a short lighter spark
  /// running along it. It is only drawn where something really flows: the chosen nav item, a
  /// decision's spine, the proof chain, the agent's connection, the door.
  ///
  /// mode   idle    the line in its quiet colour, no spark
  ///        dim     a dashed line: not connected, paused, not reached
  ///        lit     the whole line in petrol, still
  ///        run     the spark runs once from the start, the line charges behind it, then `onarrive`
  ///        listen  a spark now and then (`pause` between passes), the line stays as `base`
  /// pulse  each change sends one extra spark along a lit or listening line (the agent's heartbeat)
  ///
  /// Everything moves with transforms on the compositor. Reduced motion: no spark, a run lands at
  /// once. A hidden tab runs nothing.
  import { onDestroy } from "svelte";
  import { CSS_EASE, DUR, hidden, reduced } from "$lib/motion";

  let {
    axis = "h",
    mode = "idle",
    tone = "paper",
    from = 0,
    level = 1,
    track,
    duration = DUR.spark,
    pause = DUR.listen,
    pulse = 0,
    base = "idle",
    thickness = 2,
    onarrive,
    onspark,
    class: cls = "",
  }: {
    axis?: "h" | "v";
    mode?: "idle" | "dim" | "lit" | "run" | "listen";
    tone?: "paper" | "band";
    /** Where a run starts charging, 0 to 1 (the part already lit stays lit). */
    from?: number;
    /** How far the line is charged when lit, and where a run stops, 0 to 1. */
    level?: number;
    /** The line under the charge, when it should differ from what the mode implies. */
    track?: "solid" | "dashed" | "none";
    duration?: number;
    pause?: number;
    pulse?: number;
    /** How a listening line looks between sparks. */
    base?: "idle" | "dim" | "lit" | "none";
    thickness?: number;
    onarrive?: () => void;
    /** Called as each spark starts (the nav's sheen follows it). */
    onspark?: () => void;
    class?: string;
  } = $props();

  let wrap = $state<HTMLElement>();
  let fill = $state<HTMLElement>();
  // The line's charge, 0 to 1, as the fill's scale.
  let charge = $state(0);
  let alive = true;
  let anims: Animation[] = [];

  const scale = (v: number) => (axis === "h" ? `scaleX(${v})` : `scaleY(${v})`);
  const slide = (p: string) => (axis === "h" ? `translateX(${p})` : `translateY(${p})`);

  function stop() {
    for (const a of anims) a.cancel();
    anims = [];
  }

  /** One spark from `start` to `end`; the fill follows it when `charging`. */
  async function spark(charging: boolean, start = 0, end = 1): Promise<void> {
    if (!wrap || reduced() || hidden() || duration <= 0) return;
    onspark?.();
    const opts: KeyframeAnimationOptions = { duration, easing: CSS_EASE.inOut, fill: "forwards" };
    const s = wrap.animate(
      [
        { transform: slide(`${(start - 1) * 100}%`), opacity: 1 },
        { transform: slide(`${(end - 1) * 100}%`), opacity: 1, offset: 0.92 },
        { transform: slide(`${(end - 1) * 100}%`), opacity: 0 },
      ],
      opts,
    );
    anims.push(s);
    if (charging && fill) {
      const f = fill.animate([{ transform: scale(start) }, { transform: scale(end) }], opts);
      anims.push(f);
    }
    try {
      await s.finished;
    } catch {
      // cancelled: a new mode took over
    }
  }

  async function listen() {
    while (alive && mode === "listen") {
      if (hidden()) {
        await new Promise((r) => setTimeout(r, 500));
        continue;
      }
      await spark(false);
      await new Promise((r) => setTimeout(r, pause));
    }
  }

  let ran = 0;
  $effect(() => {
    const m = mode;
    stop();
    const to = level;
    if (m === "lit") charge = to;
    else if (m === "run") {
      const id = ++ran;
      const start = from;
      charge = start;
      void spark(true, start, to).then(() => {
        if (id !== ran || !alive) return;
        // The run's own fill holds the end until the next mode; the charge matches it underneath.
        charge = to;
        onarrive?.();
      });
    } else if (m === "listen") {
      charge = base === "lit" ? 1 : 0;
      void listen();
    } else charge = 0;
  });

  // The heartbeat: one more spark per change of `pulse`, never on the first render.
  let lastPulse: number | null = null;
  $effect(() => {
    const p = pulse;
    if (lastPulse !== null && p !== lastPulse && mode !== "run") void spark(false);
    lastPulse = p;
  });

  onDestroy(() => {
    alive = false;
    stop();
  });

  const look = $derived(
    track === "dashed" ? "dim" : track === "none" ? "none" : track === "solid" ? "idle" : mode === "listen" ? base : mode === "run" ? "lit" : mode,
  );
</script>

<span
  class="cur {cls}"
  class:v={axis === "v"}
  class:band={tone === "band"}
  class:dim={look === "dim"}
  class:bare={look === "none"}
  style:--cur-t="{thickness}px"
  aria-hidden="true"
>
  <span class="cur-line"></span>
  <span class="cur-fill" bind:this={fill} style:transform={scale(charge)}></span>
  <span class="cur-run" bind:this={wrap}><span class="cur-spark"></span></span>
</span>

<style>
  .cur {
    position: relative;
    display: block;
    overflow: hidden;
    width: 100%;
    height: var(--cur-t);
    pointer-events: none;
  }
  .cur.v {
    width: var(--cur-t);
    height: 100%;
  }
  .cur-line,
  .cur-fill,
  .cur-run {
    position: absolute;
    inset: 0;
  }
  .cur-line {
    background: var(--v-line-strong);
  }
  .cur.bare .cur-line {
    display: none;
  }
  .cur.dim .cur-line {
    background: none;
    border-top: var(--cur-t) dashed var(--v-current-dim);
  }
  .cur.v.dim .cur-line {
    border-top: 0;
    border-left: var(--cur-t) dashed var(--v-current-dim);
  }
  .cur-fill {
    background: var(--v-current);
    transform-origin: left center;
    transition: transform var(--v-dur-ui) var(--v-ease-out);
  }
  .cur.v .cur-fill {
    transform-origin: center top;
  }
  .cur-run {
    transform: translateX(-100%);
    opacity: 0;
  }
  .cur.v .cur-run {
    transform: translateY(-100%);
  }
  .cur-spark {
    position: absolute;
    right: 0;
    top: 0;
    bottom: 0;
    width: 32px;
    background: var(--v-current-spark);
  }
  .cur.v .cur-spark {
    left: 0;
    right: 0;
    top: auto;
    width: auto;
    height: 32px;
  }
  /* On the petrol band: the line is the band's muted white, the spark pure white. */
  .cur.band .cur-line {
    background: var(--valio-band-muted);
    opacity: 0.55;
  }
  .cur.band .cur-fill {
    background: var(--valio-band-fg);
  }
  .cur.band .cur-spark {
    background: var(--v-current-band);
  }
</style>
