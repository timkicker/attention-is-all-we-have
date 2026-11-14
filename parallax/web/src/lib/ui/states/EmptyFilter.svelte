<script lang="ts">
  // Filter shows nothing (wf/12): "No statement matches “q” on <date>" + Clear search. Owner: P4.
  import * as copy from '../../copy'
  import { TID } from '../../testids'

  /** q = the search text, date = YYYY-MM-DD or null (today), onclear empties the search.
   *  bare drops the own padding (when a wrapper already spaces it, as on /dev/states). */
  let { q, date, onclear, bare = false }: { q: string; date: string | null; onclear: () => void; bare?: boolean } = $props()
</script>

<div class="st" class:bare data-testid={TID.stateEmptyFilter}>
  <p>{copy.states.noMatch(q, date)}</p>
  <p><button class="u sec" type="button" data-testid={TID.stateClearSearch} onclick={onclear}>{copy.states.CLEAR_SEARCH}</button></p>
</div>

<style>
  .st { padding: 40px 0 48px; }
  .st.bare { padding: 0; }
  p + p { margin-top: 8px; }
</style>
