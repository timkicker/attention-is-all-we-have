<script lang="ts">
  // Date before the article existed (wf/12). Owner: P4.
  import * as copy from '../../copy'
  import type { Lang } from '../../model'
  import { TID } from '../../testids'

  /** lang had no article on date; it starts on startsOn; href shows every edition on startsOn. */
  /** bare drops the own padding (when a wrapper already spaces it, as on /dev/states). */
  let { lang, date, startsOn, href, bare = false }: { lang: Lang; date: string; startsOn: string; href: string; bare?: boolean } = $props()
</script>

<div class="st" class:bare data-testid={TID.stateBeforeArticle}>
  <p>{copy.states.beforeArticle(lang, date, startsOn)}</p>
  <p><a class="u sec" {href} data-testid={TID.stateBeforeArticleLink}>{copy.states.showEveryEditionOn(startsOn)}</a></p>
</div>

<style>
  .st { padding: 40px 0 48px; }
  .st.bare { padding: 0; }
  p + p { margin-top: 8px; }
</style>
