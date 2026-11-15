<script lang="ts">
  /// Whether this page is live (plans/020): still when all is well, a word that changes when not.
  import { onDestroy } from "svelte";
  import { blurSwap } from "$lib/motion";
  import { net, tick } from "$lib/net.svelte";
  import Tip from "./Tip.svelte";

  let { compact = false }: { compact?: boolean } = $props();
  const stop = tick(1000);
  onDestroy(stop);

  const state = $derived(!net.online ? "off" : net.lastOk && !net.failing && net.now - net.lastOk < 6000 ? "live" : net.lastOk ? "late" : "wait");
  const WORD = { live: "Live", late: "Reconnecting", off: "Offline", wait: "Connecting" } as const;
  const word = $derived(WORD[state]);
  const ago = $derived(net.lastOk ? Math.max(0, Math.round((net.now - net.lastOk) / 1000)) : null);
  const tip = $derived(ago == null ? "Not updated yet" : ago < 2 ? "Updated just now" : `Updated ${ago} s ago`);
</script>

<Tip text={tip}>
  {#snippet children(props)}
    <span {...props} class="lm" class:live={state === "live"} data-testid="live-mark" role="status" aria-label={compact ? word : undefined}>
      <span class="sq" aria-hidden="true"></span>
      {#if !compact}<span class="w">{#key word}<span in:blurSwap>{word}</span>{/key}</span>{/if}
    </span>
  {/snippet}
</Tip>

<style>
  .lm {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    align-self: center;
    font-size: var(--fs-cap);
    line-height: 16px;
    color: var(--valio-band-muted);
    white-space: nowrap;
  }
  .sq {
    width: 6px;
    height: 6px;
    border: 1px solid var(--valio-band-muted);
    border-radius: var(--radius-chip);
    transition:
      background-color var(--duration-fast) ease,
      border-color var(--duration-fast) ease;
  }
  .live .sq {
    background: var(--valio-band-fg);
    border-color: var(--valio-band-fg);
  }
  .w {
    display: inline-grid;
  }
  .w > span {
    grid-area: 1 / 1;
  }
</style>
