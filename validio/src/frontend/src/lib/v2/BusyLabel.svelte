<script lang="ts">
  /// A button's label while its work runs (plans/018): the working word swaps in at once, a
  /// spinner fades in only after 300 ms (a fast answer never flashes it), and the button keeps
  /// the width of its idle label.
  import { LoaderCircle } from "@lucide/svelte";
  import { blurSwap } from "$lib/motion";

  let { busy = false, idle, working }: { busy?: boolean; idle: string; working: string } = $props();
  let width = $state(0);
</script>

<span class="bl" style:min-width={width ? `${width}px` : undefined}>
  {#if busy}
    <span class="bl-in" in:blurSwap={{ duration: 160 }}><LoaderCircle class="bl-spin" size={14} aria-hidden="true" />{working}</span>
  {:else}
    <span class="bl-in" bind:offsetWidth={null, (w) => (width = Math.max(width, w ?? 0))}>{idle}</span>
  {/if}
</span>

<style>
  .bl {
    display: inline-flex;
    justify-content: center;
  }
  .bl-in {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  .bl :global(.bl-spin) {
    animation:
      v-spin 800ms linear infinite,
      v-fade-in 150ms ease 300ms both;
  }
  @media (prefers-reduced-motion: reduce) {
    .bl :global(.bl-spin) {
      animation: v-fade-in 150ms ease 300ms both;
    }
  }
</style>
