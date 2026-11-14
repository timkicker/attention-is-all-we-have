<script lang="ts">
  // Loading state (wf/12): grey bars in hairline rows. Owner: P4.
  import * as copy from '../../copy'
  import { TID } from '../../testids'

  /** rows = how many placeholder rows. */
  let { rows = 3 }: { rows?: number } = $props()
  const widths = [[88, 40], [76, 32], [82, 48]]
</script>

<div data-testid={TID.stateSkeleton} aria-busy="true">
  <span class="sr-only">{copy.states.LOADING}</span>
  {#each Array.from({ length: rows }) as _, i (i)}
    <div class="sk"><i style:width="{widths[i % 3][0]}%"></i><i style:width="{widths[i % 3][1]}%"></i></div>
  {/each}
</div>

<style>
  .sk { padding: 24px 0; border-bottom: 1px solid var(--line); }
  .sk i { display: block; height: 16px; border-radius: 4px; background: var(--soft); }
  .sk i + i { margin-top: 12px; }
</style>
