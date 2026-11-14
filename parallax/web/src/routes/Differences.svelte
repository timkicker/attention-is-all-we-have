<script lang="ts">
  // Differences tab (wf/05) and the same tab on a past date (wf/07): Finnish statements that at least one
  // other edition tells differently, differing part marked. ?q= filters, ?date= picks the date.
  import * as copy from '../lib/copy'
  import { getCounts, getDifferences, resolveTopic } from '../lib/data'
  import { dateState } from '../lib/date.svelte'
  import type { DiffRow, DifferencesVM, Failure, TabCounts } from '../lib/model'
  import { paths, router } from '../lib/router.svelte'
  import { TID } from '../lib/testids'
  import ErrorLine from '../lib/topic/ErrorLine.svelte'
  import AsOf from '../lib/ui/AsOf.svelte'
  import Bar from '../lib/ui/Bar.svelte'
  import Button from '../lib/ui/Button.svelte'
  import Field from '../lib/ui/Field.svelte'
  import Footer from '../lib/ui/Footer.svelte'
  import Item from '../lib/ui/Item.svelte'
  import Marked from '../lib/ui/Marked.svelte'
  import NoteLine from '../lib/ui/NoteLine.svelte'
  import Notice from '../lib/ui/Notice.svelte'
  import BeforeArticle from '../lib/ui/states/BeforeArticle.svelte'
  import EmptyFilter from '../lib/ui/states/EmptyFilter.svelte'
  import Skeleton from '../lib/ui/states/Skeleton.svelte'
  import TopicHeader from '../lib/ui/TopicHeader.svelte'

  let { params }: { params: Record<string, string> } = $props()

  let vm = $state<DifferencesVM | null>(null)
  let rows = $state<DiffRow[]>([])
  let failure = $state<Failure | null>(null)
  let loading = $state(true)
  let busy = $state(false)
  let title = $state('')
  let counts = $state<TabCounts>({ differences: null, removed: null })
  let q = $state(router.query.get('q') ?? '')

  const qParam = $derived(router.query.get('q') ?? '')

  $effect(() => {
    resolveTopic(params.qid).then((r) => {
      if (!title) title = r.ok ? r.data.title : params.qid
    })
  })

  // The tab counts load on their own (Removed can be slow); the list does not wait for them.
  $effect(() => {
    const date = dateState.value
    let live = true
    counts = { differences: null, removed: null }
    getCounts(params.qid, date).then((c) => {
      if (live) counts = c
    })
    return () => (live = false)
  })

  $effect(() => {
    const date = dateState.value
    const query = qParam
    let live = true
    loading = true
    failure = null
    getDifferences(params.qid, date, { q: query, offset: 0 }).then((r) => {
      if (!live) return
      loading = false
      if (!r.ok) {
        failure = r.error
        vm = null
        rows = []
        return
      }
      vm = r.data
      rows = r.data.rows
      title = r.data.topic.title
    })
    return () => (live = false)
  })

  async function more() {
    if (!vm || busy) return
    busy = true
    const r = await getDifferences(params.qid, dateState.value, { q: qParam, offset: rows.length })
    busy = false
    if (!r.ok) {
      failure = r.error
      return
    }
    const seen = new Set(rows.map((x) => x.id))
    const fresh = r.data.rows.filter((x) => !seen.has(x.id))
    rows = [...rows, ...fresh]
    vm = { ...r.data, more: fresh.length ? r.data.more : 0 }
  }

  let timer: ReturnType<typeof setTimeout> | undefined
  function onInput(v: string) {
    clearTimeout(timer)
    timer = setTimeout(() => router.setQuery({ q: v.trim() ? v : null }, { replace: true }), 200)
  }
  function clear() {
    q = ''
    clearTimeout(timer)
    router.setQuery({ q: null }, { replace: true })
  }
</script>

<Bar right="change" />
<main class="col">
  <TopicHeader
    qid={params.qid}
    {title}
    subtitle={copy.topic.SUB_DIFFERENCES}
    mark={copy.topic.SUB_DIFFERENCES_MARK}
    active="differences"
    {counts}
  />

  {#if dateState.value}
    <div class="past">
      <Notice testid={TID.noticePast}>
        {copy.showingDate(dateState.value, vm?.past?.missing ?? [])}
        {#snippet action()}
          <a class="sec u" href={paths.differencesOn(params.qid, null)} data-testid={TID.backToToday}>{copy.BACK_TO_TODAY}</a>
        {/snippet}
      </Notice>
    </div>
  {/if}

  <div class="ctl">
    <Field bind:value={q} placeholder={copy.FIND_STATEMENT} placeholderShort={copy.SEARCH_SHORT} label={copy.FIND_STATEMENT} testid={TID.findStatement} oninput={onInput} />
    <AsOf />
  </div>

  {#if loading}
    <div class="list"><Skeleton rows={3} /></div>
  {:else if failure}
    <ErrorLine {failure} />
  {:else if vm?.beforeArticle && dateState.value}
    <BeforeArticle
      lang={vm.beforeArticle.lang}
      date={dateState.value}
      startsOn={vm.beforeArticle.startsOn}
      href={paths.differencesOn(params.qid, vm.beforeArticle.startsOn)}
    />
  {:else if vm && !rows.length && qParam}
    <EmptyFilter q={qParam} date={dateState.value} onclear={clear} />
  {:else if vm && !rows.length}
    <p class="none sec">{copy.topic.NO_DIFFERENCES}</p>
  {:else}
    <div class="list">
      {#each rows as r (r.id)}
        <Item href={r.href} testid={TID.diffRow}>
          <p class="say clamp3"><Marked value={r.say} /></p>
          <NoteLine parts={r.note} />
        </Item>
      {/each}
    </div>
    {#if vm && vm.more > 0}
      <p class="more"><Button testid={TID.showMore} disabled={busy} onclick={more}>{copy.showMore(vm.more)}</Button></p>
    {/if}
  {/if}

  <Footer fromQid={params.qid} />
</main>

<style>
  .ctl { display: flex; gap: 12px; margin-top: 24px; }
  .ctl :global(.field) { flex: 1 1 auto; }
  .more { margin-top: 24px; }
  .past :global(.notice) { margin-top: 24px; }
  .none { padding: 40px 0 48px; }
  @media (max-width: 600px) {
    .ctl { gap: 8px; }
    .ctl :global(.field) { min-width: 0; }
  }
  .clamp3 { display: -webkit-box; -webkit-line-clamp: 3; line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
</style>
