<script lang="ts">
  /// The Spend Pass as one bar: the kit Progress scaled to the hard cap, with
  /// a tick where the agent stops being allowed to order alone.
  import { Progress } from "@arlen/ui-kit/components/ui/progress";
  import { money } from "$lib/format";

  let { spentCents, autoLimitCents, hardCapCents, id }: { spentCents: number; autoLimitCents: number; hardCapCents: number; id?: string } = $props();

  const pct = $derived((spentCents / hardCapCents) * 100);
  const tick = $derived((autoLimitCents / hardCapCents) * 100);
</script>

<div class="spend" {id}>
  <div class="head">
    <span><span class="v num">{money(spentCents)}</span> <span class="l">of {money(autoLimitCents)} allowed alone</span></span>
    <span class="l num">cap {money(hardCapCents)}</span>
  </div>
  <div class="track">
    <Progress value={pct} label="Spent against the Spend Pass" />
    <span class="tick" style="left: {tick}%" aria-hidden="true"></span>
  </div>
</div>

<style>
  .spend {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .head {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    font-size: var(--text-xs);
  }
  .v {
    color: var(--color-fg-primary);
    font-weight: 500;
  }
  .l {
    color: var(--color-fg-secondary);
  }
  .track {
    position: relative;
  }
  .tick {
    position: absolute;
    top: -3px;
    width: 2px;
    height: 12px;
    margin-left: -1px;
    background: var(--color-fg-secondary);
  }
</style>
