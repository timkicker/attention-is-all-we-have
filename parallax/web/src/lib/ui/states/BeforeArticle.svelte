<script lang="ts">
  // Date before the article existed (wf/12). Owner: P4.
  import * as copy from '../../copy'
  import type { Lang } from '../../model'
  import { TID } from '../../testids'

  /** lang had no article on date; it starts on startsOn; href shows every edition on startsOn. */
  let { lang, date, startsOn, href }: { lang: Lang; date: string; startsOn: string; href: string } = $props()
</script>

<div class="st" data-testid={TID.stateBeforeArticle}>
  <p>{copy.states.beforeArticle(lang, date, startsOn)}</p>
  <p><a class="u sec" {href} data-testid={TID.stateBeforeArticleLink}>{copy.states.showEveryEditionOn(startsOn)}</a></p>
</div>

<style>
  .st { padding: 40px 0 48px; }
  p + p { margin-top: 8px; }
</style>
