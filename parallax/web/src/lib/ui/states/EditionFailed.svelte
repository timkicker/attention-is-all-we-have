<script lang="ts">
  // One edition failed (wf/12): notice with reason, how many others are ready, an open link, retry time. Owner: P4.
  import * as copy from '../../copy'
  import type { Lang } from '../../model'
  import { TID } from '../../testids'

  let {
    lang,
    rateLimited = false,
    othersReady,
    openHref = null,
    retryInS = null,
  }: {
    /** The edition that failed. */
    lang: Lang
    /** true when Wikipedia asked us to slow down (429). */
    rateLimited?: boolean
    /** Editions that are ready ("The other six are ready"). */
    othersReady: number
    /** Link to open the ready ones; null hides "Open them". */
    openHref?: string | null
    /** Seconds to the next retry; null hides "Retrying in". */
    retryInS?: number | null
  } = $props()
</script>

<div class="notice" role="status" data-testid={TID.stateEditionFailed}>
  <span class="text"
    >{copy.states.editionFailed(lang, rateLimited)}<span class="sec parts"
      ><span>{copy.states.othersReady(othersReady)}</span>{#if openHref}<a class="u" href={openHref} data-testid={TID.stateEditionFailedOpen}
          >{copy.states.OPEN_THEM}</a
        >{/if}</span
    ></span
  >
  {#if retryInS !== null}<span class="muted">{copy.states.retryingIn(retryInS)}</span>{/if}
</div>

<style>
  .text { flex: 1; }
  .muted { white-space: nowrap; }
  @media (max-width: 600px) {
    .notice { flex-direction: column; align-items: flex-start; gap: 4px; }
  }
</style>
