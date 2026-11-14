<script lang="ts">
  // Filter shows nothing (wf/12): "No statement matches “q” on <date>" + Clear search. Owner: P4.
  import * as copy from '../../copy'
  import { TID } from '../../testids'

  /** q = the search text, date = YYYY-MM-DD or null (today), onclear empties the search. */
  let { q, date, onclear }: { q: string; date: string | null; onclear: () => void } = $props()
</script>

<div class="st" data-testid={TID.stateEmptyFilter}>
  <p>{copy.states.noMatch(q, date)}</p>
  <p><button class="u sec" type="button" data-testid={TID.stateClearSearch} onclick={onclear}>{copy.states.CLEAR_SEARCH}</button></p>
</div>

<style>
  .st { padding: 40px 0 48px; }
  p + p { margin-top: 8px; }
</style>
