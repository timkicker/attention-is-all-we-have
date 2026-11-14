<script lang="ts">
  // Dev-only page for screenshot 12. Owner: P4. The four states stacked, with the wireframe's
  // example values from fixture.STATES_EXAMPLE.
  import * as copy from '../lib/copy'
  import { STATES_EXAMPLE, WINTER_WAR } from '../lib/fixture'
  import { paths } from '../lib/router.svelte'
  import Bar from '../lib/ui/Bar.svelte'
  import Footer from '../lib/ui/Footer.svelte'
  import TopicHeader from '../lib/ui/TopicHeader.svelte'
  import BeforeArticle from '../lib/ui/states/BeforeArticle.svelte'
  import EditionFailed from '../lib/ui/states/EditionFailed.svelte'
  import EmptyFilter from '../lib/ui/states/EmptyFilter.svelte'
  import Skeleton from '../lib/ui/states/Skeleton.svelte'

  let { params: _params }: { params: Record<string, string> } = $props()
  const ex = STATES_EXAMPLE
</script>

<Bar right="change" />
<main class="col">
  <section class="st first">
    <p class="cap t13">{copy.states.CAP_LOADING}</p>
    <TopicHeader qid={WINTER_WAR.qid} title={WINTER_WAR.title} subtitle={copy.topic.SUB_DIFFERENCES} mark={copy.topic.SUB_DIFFERENCES_MARK} active="differences" />
    <Skeleton />
  </section>
  <section class="st">
    <p class="cap t13">{copy.states.CAP_EMPTY}</p>
    <EmptyFilter q={ex.emptyFilter.q} date={ex.emptyFilter.date} onclear={() => {}} bare />
  </section>
  <section class="st">
    <p class="cap t13">{copy.states.CAP_FAILED}</p>
    <EditionFailed lang={ex.editionFailed.lang} rateLimited={ex.editionFailed.rateLimited} othersReady={ex.editionFailed.othersReady} openHref={paths.differences(WINTER_WAR.qid)} retryInS={ex.editionFailed.retryInS} />
  </section>
  <section class="st">
    <p class="cap t13">{copy.states.CAP_BEFORE}</p>
    <BeforeArticle lang={ex.beforeArticle.lang} date={ex.beforeArticle.date} startsOn={ex.beforeArticle.startsOn} href={paths.differencesOn(WINTER_WAR.qid, ex.beforeArticle.startsOn)} bare />
  </section>
  <Footer />
</main>

<style>
  .st { padding: 40px 0 48px; border-bottom: 1px solid var(--line); }
  .st.first { padding-top: 24px; }
  .st:last-of-type { border-bottom: 0; }
  .cap { margin-bottom: 16px; font-family: var(--mono); color: var(--fg3); }
</style>
