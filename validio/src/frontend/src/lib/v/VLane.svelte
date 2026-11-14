<script lang="ts">
  /// A record lane: name, value and an optional sub on the left, exactly one plot on the right.
  import type { Snippet } from "svelte";

  let { name, value, sub, testid, plot }: { name: string; value: string; sub?: string; testid?: string; plot: Snippet } = $props();
</script>

<div class="rc-lane" data-testid={testid}>
  <div class="rc-lab">
    <div class="rc-n">{name}</div>
    <div class="rc-v">{value}</div>
    {#if sub}<div class="rc-s">{sub}</div>{/if}
  </div>
  {@render plot()}
</div>
