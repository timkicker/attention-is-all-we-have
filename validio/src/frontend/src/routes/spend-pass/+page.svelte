<script lang="ts">
  // The authority the kitchen gave its agent, laid out as Arlen settings lays
  // out an app's access: what it may do, the value, and whether the agent
  // showed it to Validio. One chart: where each request fell on the scale.
  import { api } from "$lib/api/client";
  import { setChrome } from "$lib/chrome.svelte";
  import { day, dayTime, money } from "$lib/format";
  import { live } from "$lib/live.svelte";
  import Frame from "$lib/components/Frame.svelte";
  import Pairs from "$lib/components/Pairs.svelte";

  setChrome("Spend Pass");
  // The bar says "Spend Pass", the heading says what the pass is.
  const pass = live(() => api.spendPass("M-1"));

  const SUBSTITUTES: Record<string, string> = {
    listed_and_rules_kept: "Valio's listed ones, when every rule holds",
    none: "None",
    any_rules_kept: "Any, when every rule holds",
  };
  const HIDDEN: Record<string, string> = {
    approvers: "Who approves",
    preferLabels: "Preferred labels",
  };


</script>

<Frame title="What the agent may buy" top>
  {#snippet head()}
    {#if pass.data}
      <p class="who" data-testid="pass-valid-to" id="pass-valid-to">Valid until {dayTime(pass.data.validTo)}</p>
    {/if}
  {/snippet}
  {#if pass.data}
    {@const p = pass.data}
    {#if p.autoLimitCents !== undefined && p.hardCapCents !== undefined}
      {@const cap = p.hardCapCents}
      {@const top = cap * 1.15}
      {@const at = (c: number) => `${Math.min(c / top, 1) * 100}%`}
      <figure class="scale" id="spend-scale">
        <div class="track" aria-hidden="true">
          <span class="zone alone" style="width: {at(p.autoLimitCents)}"></span>
          <span class="zone ask" style="left: {at(p.autoLimitCents)}; width: calc({at(cap)} - {at(p.autoLimitCents)})"></span>
          <span class="zone over" style="left: {at(cap)}"></span>
          <span class="tick" style="left: {at(p.autoLimitCents)}"></span>
          <span class="tick cap" style="left: {at(cap)}"></span>
        </div>
        <figcaption class="legend">
          <span data-testid="pass-auto" id="pass-auto">Alone up to <b class="num">{money(p.autoLimitCents)}</b></span>
          <span data-testid="pass-cap" id="pass-cap">Asks you up to <b class="num">{money(cap)}</b></span>
          <span>Blocked above</span>
        </figcaption>
      </figure>
    {/if}

    <Pairs
      items={[
        ...(p.diet?.length ? [{ label: "Diet", value: p.diet.map((d) => d.replaceAll("_", " ")).join(", "), id: "pass-diet" }] : []),
        ...(p.deliverBy ? [{ label: "Delivered by", value: day(p.deliverBy), id: "pass-deliver-by" }] : []),
        ...(p.substitutes ? [{ label: "Substitutes", value: SUBSTITUTES[p.substitutes] ?? p.substitutes.replaceAll("_", " ") }] : []),
        { label: "Splitting a line", value: `up to ${p.split.maxExtraCostPct}\u00a0% more`, note: p.split.allowListedSubstitutes ? "with Valio's listed substitutes" : "same product only" },
      ]}
    />
    {#if p.hidden.length}
      <p class="legend-line" data-testid="pass-approvers" id="pass-approvers">
        Hidden from Validio: {p.hidden.map((h) => (HIDDEN[h] ?? h).toLowerCase()).join(" and ")}.
      </p>
    {/if}
  {:else if pass.error}
    <p class="t-quiet">Cannot read the Spend Pass: {pass.error}</p>
  {/if}
</Frame>

<style>
  .who {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.35rem;
    margin: 0;
    font-size: var(--text-sm);
    color: var(--color-fg-secondary);
  }
  .legend-line {
    margin: 0;
    font-size: var(--text-xs);
    color: var(--color-fg-secondary);
  }
  .scale {
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
    margin: 0;
    padding-top: 1.4rem;
  }
  .track {
    position: relative;
    height: 0.5rem;
    border-radius: var(--radius-full);
    overflow: visible;
  }
  .zone {
    position: absolute;
    top: 0;
    bottom: 0;
  }
  .zone.alone {
    left: 0;
    border-radius: var(--radius-full) 0 0 var(--radius-full);
    background: var(--color-fg-primary);
  }
  .zone.ask {
    background: color-mix(in srgb, var(--color-fg-primary) 18%, transparent);
  }
  .zone.over {
    right: 0;
    border-radius: 0 var(--radius-full) var(--radius-full) 0;
    background: repeating-linear-gradient(135deg, color-mix(in srgb, var(--color-fg-primary) 22%, transparent) 0 2px, transparent 2px 5px);
  }
  .tick {
    position: absolute;
    top: -3px;
    bottom: -3px;
    width: 2px;
    margin-left: -1px;
    background: var(--color-fg-secondary);
  }
  .legend {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    font-size: var(--text-xs);
    color: var(--color-fg-secondary);
  }
  .legend b {
    font-weight: 500;
    color: var(--color-fg-primary);
  }
  @media (max-width: 760px) {
    .legend {
      flex-direction: column;
      gap: 0.15rem;
    }
  }
</style>
