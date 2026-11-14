<script lang="ts">
  // Start (wf 01, 02): hero, the big search with its result popover, the example and the prepared articles.
  import { onMount } from 'svelte'
  import * as copy from '../lib/copy'
  import { getStart, search, startIngest } from '../lib/data'
  import type { SearchResult, SearchVM, StartVM } from '../lib/model'
  import { router } from '../lib/router.svelte'
  import { TID } from '../lib/testids'
  import Bar from '../lib/ui/Bar.svelte'
  import Field from '../lib/ui/Field.svelte'
  import Footer from '../lib/ui/Footer.svelte'
  import Marked from '../lib/ui/Marked.svelte'
  import SearchResults from '../lib/start/SearchResults.svelte'

  let { params: _params }: { params: Record<string, string> } = $props()

  let vm = $state<StartVM | null>(null)
  let q = $state(router.query.get('q') ?? '')
  let found = $state<SearchVM | null>(null)
  let searching = $state(false)
  let failed = $state<string | null>(null)
  let open = $state(false)
  let active = $state(0)
  let input = $state<HTMLInputElement>()
  let wrap = $state<HTMLDivElement>()
  let timer: ReturnType<typeof setTimeout> | undefined
  let seq = 0

  onMount(() => {
    getStart().then((r) => {
      if (r.ok) vm = r.data
    })
    if (q.trim()) {
      runSearch(q)
      input?.focus()
    }
    return () => clearTimeout(timer)
  })

  async function runSearch(text: string) {
    const mine = ++seq
    searching = true
    failed = null
    const r = await search(text)
    if (mine !== seq) return
    searching = false
    if (r.ok) {
      found = r.data
      active = 0
    } else {
      found = null
      failed = r.error.code === 'rate_limited' && r.error.retryAfterS ? copy.ERR.rateLimited(r.error.retryAfterS) : copy.start.SEARCH_FAILED
    }
    open = true
  }

  function onInput(value: string) {
    clearTimeout(timer)
    router.setQuery({ q: value.trim() ? value : null }, { replace: true })
    if (!value.trim()) {
      seq++
      found = null
      searching = false
      open = false
      return
    }
    timer = setTimeout(() => runSearch(value), 250)
  }

  // The wireframe shows at most four results.
  const results = $derived((found?.results ?? []).slice(0, 4))

  async function choose(r: SearchResult) {
    if (!r.href) return
    if (r.status === 'new') {
      const s = await startIngest(r.qid)
      if (!s.ok && s.error.code === 'rate_limited') {
        failed = copy.ERR.rateLimited(s.error.retryAfterS ?? 120)
        return
      }
      if (!s.ok && s.error.code === 'no_finnish') {
        failed = copy.start.NO_FINNISH_LONG
        return
      }
    }
    router.navigate(r.href)
  }

  function onKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      // A search input clears itself on Escape; here Escape only closes the results.
      e.preventDefault()
      open = false
      return
    }
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      if (!results.length) return
      e.preventDefault()
      open = true
      const step = e.key === 'ArrowDown' ? 1 : -1
      active = (active + step + results.length) % results.length
      return
    }
    if (e.key === 'Enter') {
      e.preventDefault()
      const r = results[active]
      if (open && r) choose(r)
    }
  }

  function onFocusOut(e: FocusEvent) {
    if (!wrap?.contains(e.relatedTarget as Node | null)) open = false
  }
</script>

<Bar right="none" />
<main class="wide">
  <!-- While the results are open, what sits under them is hidden (layout kept), so no row peeks out below. -->
  <div class="split" class:covered={open && !!q.trim()}>
    <section class="intro">
      <h1 class="hero">{copy.start.HERO}</h1>
      <p class="sec t18">{copy.start.LEAD}</p>
      <div class="search" bind:this={wrap} onfocusout={onFocusOut}>
        <Field
          big
          bind:value={q}
          bind:input
          placeholder={copy.start.SEARCH_PLACEHOLDER}
          label={copy.start.SEARCH_LABEL}
          testid={TID.startSearch}
          oninput={onInput}
          onkeydown={onKeydown}
          onfocus={() => {
            if (q.trim() && (found || failed)) open = true
          }}
        />
        {#if open && q.trim()}
          <SearchResults {results} {active} {searching} {failed} onchoose={choose} onhover={(i) => (active = i)} />
        {/if}
      </div>
    </section>

    {#if vm?.example}
      {@const ex = vm.example}
      <a class="ex" href={ex.href} data-testid={TID.startExample}>
        <p class="t13 muted">{copy.start.exampleKicker(ex.topic.title)}</p>
        <p>{ex.title}</p>
        {#each ex.lines as l (l.lang)}
          <div class="line"><p class="t13 muted">{copy.edition(l.lang)}</p><p class="say"><Marked value={l.say} /></p></div>
        {/each}
        <span class="go" data-testid={TID.startExampleOpen}>{copy.start.OPEN_EXAMPLE}</span>
      </a>
    {/if}

    {#if vm && vm.prepared.length}
      <section class="pre">
        <p class="sec">{copy.start.PREPARED_LEAD}</p>
        <nav class="topics">
          {#each vm.prepared as t (t.qid)}
            <a href={t.href} data-testid={TID.startPrepared}><span>{t.title}</span><span class="muted num">{t.from !== null ? copy.years(t.from, t.to) : 'editions' in t ? copy.start.editionCount(t.editions as number) : ''}</span></a>
          {/each}
        </nav>
      </section>
    {/if}
  </div>

  <Footer />
</main>

<style>
  .split { display: grid; grid-template-columns: minmax(0, 1fr) 400px; grid-template-areas: "intro ex" "topics ex"; grid-template-rows: auto 1fr; column-gap: 96px; padding-top: 72px; align-items: start; }
  .intro { grid-area: intro; }
  .pre { grid-area: topics; margin-top: 40px; }
  .ex { grid-area: ex; display: block; padding-top: 8px; }
  .intro > .sec { margin-top: 12px; }
  .search { position: relative; margin-top: 32px; }
  .covered .pre { visibility: hidden; }
  .topics { margin-top: 8px; border-top: 1px solid var(--line); }
  .topics a { display: flex; justify-content: space-between; gap: 16px; padding: 12px 0; border-bottom: 1px solid var(--line); }
  .ex .line { margin-top: 20px; }
  .ex .say { font: 400 var(--fs-18)/28px var(--serif); display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 4; line-clamp: 4; overflow: hidden; }
  .ex .go { display: inline-block; margin-top: 24px; font-weight: 500; }
  @media (max-width: 1000px) {
    .split { grid-template-columns: minmax(0, 1fr); grid-template-areas: "intro" "topics" "ex"; }
    .ex { margin-top: 48px; }
    .covered .ex { visibility: hidden; }
    .pre { margin-top: 56px; }
  }
  @media (max-width: 600px) {
    .split { padding-top: 32px; }
    .search { margin-top: 24px; }
    .search :global(.field.big) { font-size: var(--fs-15); }
    .ex .say { font-size: 17px; line-height: 26px; }
  }
</style>
