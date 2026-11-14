<script lang="ts">
  // The one footer line. 'full' everywhere (05), 'short' on Under the hood (11): no machine line, no link.
  // fromQid makes the Under the hood link come back to this topic.
  import * as copy from '../copy'
  import { paths } from '../router.svelte'
  import { TID } from '../testids'

  let { variant = 'full', fromQid = null }: { variant?: 'full' | 'short'; fromQid?: string | null } = $props()
</script>

<p class="foot" data-testid={TID.foot}>
  {#if variant === 'full'}
    {copy.FOOT.licence}{copy.FOOT.sep}{copy.FOOT.machine}{copy.FOOT.sep}{copy.FOOT.affiliation}{copy.FOOT.sep}<a
      href={paths.hood(fromQid)}
      data-testid={TID.footHood}>{copy.FOOT.hood}</a
    >
  {:else}
    {copy.FOOT.licence}{copy.FOOT.sep}{copy.FOOT.affiliation}
  {/if}
</p>
