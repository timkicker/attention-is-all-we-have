<script lang="ts">
  // Removed tab (wf/08): statements one edition removed while others still have them.
  // Filters live in the URL: ?q= (find a statement), ?edition= (lang), ?offset= (rows "Show N more" added).
  // The page shows FIRST rows, then STEP more per click; the adapter is asked for at least that many.
  import * as copy from '../lib/copy'
  import { getRemoved, resolveTopic } from '../lib/data'
  import { dateState } from '../lib/date.svelte'
  import { LANGS, type Lang, type RemovedVM, type Result, type TabCounts } from '../lib/model'
  import EditionPick from '../lib/removed/EditionPick.svelte'
  import { router } from '../lib/router.svelte'
  import { TID } from '../lib/testids'
  import AsOf from '../lib/ui/AsOf.svelte'
  import Bar from '../lib/ui/Bar.svelte'
  import Field from '../lib/ui/Field.svelte'
  import Footer from '../lib/ui/Footer.svelte'
  import Item from '../lib/ui/Item.svelte'
  import type { MarkedText, RemovedRow } from '../lib/model'
  import Marked from '../lib/ui/Marked.svelte'
  import NoteLine from '../lib/ui/NoteLine.svelte'
  import Skeleton from '../lib/ui/states/Skeleton.svelte'
  import EmptyFilter from '../lib/ui/states/EmptyFilter.svelte'
  import TopicHeader from '../lib/ui/TopicHeader.svelte'

  let { params }: { params: Record<string, string> } = $props()

  const asLang = (s: string | null): Lang | null => (s && (LANGS as readonly string[]).includes(s) ? (s as Lang) : null)

  let res = $state<Result<RemovedVM> | null>(null)
  let title = $state('')
  let counts = $state<TabCounts>({ differences: null, removed: null })
  let q = $state(router.query.get('q') ?? '')

  const qParam = $derived(router.query.get('q') ?? '')
  const edition = $derived(asLang(router.query.get('edition')))
  const FIRST = 5
  const STEP = 25
  const offset = $derived(Math.max(0, Number(router.query.get('offset')) || 0))
  const shown = $derived(FIRST + offset)
  // A partial cut of only a unit or one short token ("km²", "%", "ca") says little: such rows go after the rest of the page.
  const UNIT = /^(km²|km2|km|m²|m|kg|t|%|ha|mi|ft|°c?)$/i
  const struck = (r: RemovedRow) => r.say.spans.map((s) => r.say.text.slice(s.start, s.end)).join(' ').replace(/[\s.,;:()]+/g, ' ').trim()
  const minor = (r: RemovedRow) => {
    const cut = struck(r)
    const whole = r.say.text.replace(/[\s.,;:()]+/g, ' ').trim()
    return cut !== whole && !cut.includes(' ') && (cut.length <= 3 || UNIT.test(cut))
  }
  // Under the 2-line clamp a struck part further in than about 2 lines would be hidden: then the text starts a little
  // before it with "…" (as focusOn in adapt/topic.ts does for 3 lines). The statement page has the whole sentence.
  let narrow = $state(typeof matchMedia === 'function' && matchMedia('(max-width: 600px)').matches)
  $effect(() => {
    if (typeof matchMedia !== 'function') return
    const mq = matchMedia('(max-width: 600px)')
    const on = () => (narrow = mq.matches)
    mq.addEventListener('change', on)
    return () => mq.removeEventListener('change', on)
  })
  function focused(say: MarkedText): MarkedText {
    const first = say.spans[0]?.start ?? 0
    if (first <= (narrow ? 50 : 120)) return say
    let at = say.text.lastIndexOf(' ', first - 24)
    if (at < 0) at = first - 24
    const cut = at + 1
    return { text: `…${say.text.slice(cut)}`, spans: say.spans.map((sp) => ({ start: sp.start - cut + 1, end: sp.end - cut + 1 })) }
  }
  const visible = $derived(
    res?.ok
      ? res.data.rows
          .slice(0, shown)
          .map((r, i) => ({ r, i, m: minor(r) ? 1 : 0 }))
          .sort((a, b) => a.m - b.m || a.i - b.i)
          .map((x) => x.r)
      : [],
  )
  const more = $derived(res?.ok ? Math.max(0, res.data.total - visible.length) : 0)

  $effect(() => {
    resolveTopic(params.qid).then((r) => (title = r.ok ? r.data.title : params.qid))
  })

  $effect(() => {
    const args = { q: qParam, offset: shown, edition }
    const date = dateState.value
    let live = true
    getRemoved(params.qid, date, args).then((r) => {
      if (!live) return
      res = r
      if (r.ok) {
        counts = r.data.counts
        title = r.data.topic.title
      }
    })
    return () => (live = false)
  })

  let timer: ReturnType<typeof setTimeout> | undefined
  function onInput(v: string) {
    clearTimeout(timer)
    timer = setTimeout(() => router.setQuery({ q: v.trim() ? v : null, offset: null }, { replace: true }), 200)
  }
  function clear() {
    q = ''
    router.setQuery({ q: null, offset: null }, { replace: true })
  }
  function showMore() {
    router.setQuery({ offset: String(offset + STEP) }, { replace: true })
  }
</script>

<Bar right="change" />
<main class="col">
  <TopicHeader qid={params.qid} {title} subtitle={copy.removed.SUB_REMOVED} active="removed" {counts} />

  <div class="ctl">
    <Field bind:value={q} placeholder={copy.FIND_STATEMENT} testid={TID.findStatement} oninput={onInput} />
    <div class="pair">
      <EditionPick value={edition} editions={res?.ok ? res.data.editions : []} onpick={(l) => router.setQuery({ edition: l, offset: null })} />
      <AsOf />
    </div>
  </div>

  {#if res === null}
    <Skeleton />
  {:else if !res.ok}
    <p class="msg sec" role="alert">{res.error.status === 404 ? copy.ERR.topicNotFound : res.error.status === 0 && res.error.code === 'network' ? copy.ERR.network : copy.ERR.generic}</p>
  {:else if !res.data.rows.length}
    {#if res.data.q}
      <EmptyFilter q={res.data.q} date={res.data.date} onclear={clear} />
    {:else}
      <p class="msg sec">{copy.removed.NO_REMOVED}</p>
    {/if}
  {:else}
    <div class="list">
      {#each visible as row (row.id)}
        <Item href={row.href} testid={TID.removedRow}>
          <p class="say"><Marked value={focused(row.say)} as="del" /></p>
          <NoteLine parts={row.note} />
        </Item>
      {/each}
    </div>
    {#if more > 0}
      <p class="more"><button class="btn" type="button" data-testid={TID.showMore} onclick={showMore}>{copy.showMore(more)}</button></p>
    {/if}
  {/if}

  <Footer fromQid={params.qid} />
</main>

<style>
  /* Two lines at most; the statement page shows the whole sentence. */
  .say { display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; line-clamp: 2; overflow: hidden; }
  .ctl { display: flex; gap: 12px; margin-top: 24px; }
  .ctl :global(.field) { flex: 1 1 auto; min-width: 0; }
  .pair { display: flex; gap: 12px; flex: none; }
  .more { margin-top: 24px; }
  .msg { padding: 40px 0 48px; }
  @media (max-width: 600px) {
    .ctl { gap: 8px; flex-wrap: wrap; }
    .ctl :global(.field) { flex: 1 1 100%; }
    .pair { gap: 8px; }
  }
</style>
