<script lang="ts">
  // One statement (wf/06): how each edition tells it, grouped by wording, and when editions changed it.
  import * as copy from '../lib/copy'
  import { getStatement } from '../lib/data'
  import { dateState } from '../lib/date.svelte'
  import type { Failure, Lang, MarkedText, StatementVM } from '../lib/model'
  import { TID } from '../lib/testids'
  import ErrorLine from '../lib/topic/ErrorLine.svelte'
  import Bar from '../lib/ui/Bar.svelte'
  import Footer from '../lib/ui/Footer.svelte'
  import Marked from '../lib/ui/Marked.svelte'
  import Skeleton from '../lib/ui/states/Skeleton.svelte'

  let { params }: { params: Record<string, string> } = $props()

  let vm = $state<StatementVM | null>(null)
  let failure = $state<Failure | null>(null)
  let original = $state(false)

  $effect(() => {
    const date = dateState.value
    let live = true
    vm = null
    failure = null
    getStatement(params.qid, date, params.lang, params.pageId, params.h).then((r) => {
      if (!live) return
      if (r.ok) vm = r.data
      else failure = r.error
    })
    return () => (live = false)
  })

  /** Original wording per edition: marked when the adapter sent marks, else the plain text. */
  function originals(g: StatementVM['groups'][number]): { lang: Lang; say: MarkedText; url: string | null }[] {
    if (g.marked.length) return g.marked
    return g.originals.map((o) => ({ lang: o.lang, say: { text: o.text, spans: [] }, url: o.url }))
  }
  const open = $derived(vm?.open ?? [])
  /** Groups whose long quote is shown in full. */
  let openQ = $state(new Set<number>())
  /** Groups whose quote is cut by the clamp (measured, so it holds at every width). */
  let cut = $state(new Set<number>())
  const overflow = (i: number) => (el: HTMLElement) => {
    const check = () => {
      const over = el.scrollHeight > el.clientHeight + 1
      if (over !== cut.has(i)) {
        const n = new Set(cut)
        if (over) n.add(i)
        else n.delete(i)
        cut = n
      }
    }
    const ro = new ResizeObserver(check)
    ro.observe(el)
    check()
    return () => ro.disconnect()
  }
  let allChanges = $state(false)
  const SHOWN = 3
  const toggle = (i: number) => {
    const n = new Set(openQ)
    if (n.has(i)) n.delete(i)
    else n.add(i)
    openQ = n
  }
  const changeRest = (c: StatementVM['changes'][number]) =>
    c.to ? copy.topic.changeRest(c.lang, c.from, c.to) : copy.topic.removedRest(c.lang)
  /** Each edition of a group with the revision its wording is from. */
  const versions = (g: StatementVM['groups'][number]) =>
    g.langs.map((l) => ({ lang: l, url: g.originals.find((o) => o.lang === l)?.url ?? null }))
  const sep = (i: number, n: number) => (i === n - 1 ? '' : i === n - 2 ? copy.topic.LIST_AND : copy.topic.LIST_SEP)
  // Test ids of the revision links on this page (not in the shared TID list).
  const VERSION = 'statement-version'
  const CHANGE_VERSION = 'change-version'
</script>

<Bar right="change" />
<main class="col">
  {#if vm}
    <a class="back sec" href={vm.backHref} data-testid={TID.statementBack}>{copy.backArrow(vm.topic.title)}</a>
    <h1 class="shead" data-testid={TID.statementTitle}>{vm.title}</h1>
    <button class="orig sec u" type="button" aria-pressed={original} data-testid={TID.showOriginal} onclick={() => (original = !original)}>
      {original ? copy.topic.SHOW_ENGLISH : copy.topic.SHOW_ORIGINAL}
    </button>

    <div class="list">
      {#each vm.groups as g, i (i)}
        <div class="item" data-testid={TID.statementGroup} data-langs={g.langs.join(',')}>
          {#if original}
            {#each originals(g) as o (o.lang)}
              <div class="one">
                <p class="ed">{#if o.url}<a class="v" href={o.url} target="_blank" rel="noopener" title={copy.topic.versionTitle(o.lang)} data-testid={VERSION}>{copy.edition(o.lang)}</a>{:else}{copy.edition(o.lang)}{/if}</p>
                <p class="say">{#if o.say.text}<Marked value={o.say} />{/if}</p>
              </div>
            {/each}
          {:else}
            <p class="ed">{#each versions(g) as v, j (v.lang)}{#if v.url}<a class="v" href={v.url} target="_blank" rel="noopener" title={copy.topic.versionTitle(v.lang)} data-testid={VERSION}>{copy.edition(v.lang)}</a>{:else}{copy.edition(v.lang)}{/if}{sep(j, g.langs.length)}{/each}{#if i > 0 && !g.say.spans.length}<span class="why">{' '}{copy.topic.saysItDifferently(g.langs.length)}</span>{/if}</p>
            <p class="say" class:clamp={!openQ.has(i)} {@attach overflow(i)}><Marked value={g.say} /></p>
            {#if cut.has(i) || openQ.has(i)}
              <button class="more sec u" type="button" aria-expanded={openQ.has(i)} onclick={() => toggle(i)}>{openQ.has(i) ? copy.topic.LESS : copy.topic.MORE}</button>
            {/if}
          {/if}
        </div>
      {/each}
      {#if vm.missing.length}
        <div class="item" data-testid={TID.statementMissing}><p class="muted">{copy.notIn(vm.missing)}</p></div>
      {/if}
      {#if open.length}
        <div class="item"><p class="muted">{copy.notCompared(open)}</p></div>
      {/if}
    </div>

    <section class="changed">
      <h2>{copy.topic.WHEN_IT_CHANGED}</h2>
      <div class="list">
        {#each allChanges ? vm.changes : vm.changes.slice(0, SHOWN) as c, i (i)}
          <div class="item" data-testid={TID.changeRow}>
            <p>{#if c.url}<a class="v" href={c.url} target="_blank" rel="noopener" title={copy.topic.versionTitle(c.lang)} data-testid={CHANGE_VERSION}>{copy.topic.changeDate(c.date, c.approx)}</a>{:else}{copy.topic.changeDate(c.date, c.approx)}{/if}</p>
            <p>{changeRest(c)}</p>
            {#if c.comment}<p class="t13 muted one-line" title={c.comment}>{copy.editComment(c.comment)}</p>{/if}
          </div>
        {:else}
          <div class="item"><p class="muted">{copy.topic.NO_CHANGES}</p></div>
        {/each}
      </div>
      {#if !allChanges && vm.changes.length > SHOWN}
        <button class="more sec u" type="button" onclick={() => (allChanges = true)}>{copy.topic.showAllChanges(vm.changes.length)}</button>
      {/if}

    </section>
  {:else if failure}
    <ErrorLine {failure} />
  {:else}
    <div class="list"><Skeleton rows={3} /></div>
  {/if}

  <Footer fromQid={params.qid} />
</main>

<style>
  .back { display: inline-block; margin-top: 24px; font-size: var(--fs-15); }
  .shead { margin-top: 8px; }
  .orig { display: inline-block; margin-top: 8px; font-size: var(--fs-15); }
  .ed { display: inline-block; font-weight: var(--w-medium); }
  .item .say { margin-top: 4px; }
  .one + .one { margin-top: 16px; }
  .clamp { display: -webkit-box; -webkit-line-clamp: 4; line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden; }
  .more { margin-top: 4px; font-size: var(--fs-15); }
  .one-line { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .v { color: inherit; text-decoration: none; }
  .why { font-weight: var(--w-regular); color: var(--fg2); }
  .v:hover, .v:focus-visible { text-decoration: underline; text-decoration-color: var(--line2); text-underline-offset: 4px; text-decoration-thickness: 1.5px; }
  .changed { margin-top: 64px; }
  .changed .item { padding: 16px 0; }
</style>
