<script lang="ts">
  // wf .notice: one quiet line on soft ground, optional action on the right (stacks on phones).
  import type { Snippet } from 'svelte'

  let { testid, children, action }: { testid?: string; children: Snippet; action?: Snippet } = $props()
</script>

<div class="notice" role="status" data-testid={testid}>
  <span class="text">{@render children()}</span>
  {#if action}<span class="act">{@render action()}</span>{/if}
</div>

<style>
  .notice { justify-content: space-between; }
  .text { flex: 1; }
  .act { white-space: nowrap; }
  @media (max-width: 600px) {
    .notice { flex-direction: column; align-items: flex-start; gap: 4px; }
  }
</style>
