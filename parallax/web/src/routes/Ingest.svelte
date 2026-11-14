<script lang="ts">
  // Ingest progress (wf 03, 04): polls the job every 2 s, offers the comparison once usable,
  // and opens the topic by itself when everything is done.
  import { onMount } from 'svelte'
  import * as copy from '../lib/copy'
  import { getIngest, startIngest } from '../lib/data'
  import type { Failure, IngestEdition, IngestVM } from '../lib/model'
  import { router } from '../lib/router.svelte'
  import { TID } from '../lib/testids'
  import Bar from '../lib/ui/Bar.svelte'
  import Button from '../lib/ui/Button.svelte'
  import Footer from '../lib/ui/Footer.svelte'
  import Notice from '../lib/ui/Notice.svelte'
  import EditionFailed from '../lib/ui/states/EditionFailed.svelte'

  let { params }: { params: Record<string, string> } = $props()
  const qid = $derived(params.qid)

  const POLL_MS = 2000

  let vm = $state<IngestVM | null>(null)
  let problem = $state<string | null>(null)
  let now = $state(Date.now())
  let busy = $state(false)
  let triedStart = false
  let timer: ReturnType<typeof setTimeout> | undefined
  let alive = true

  function explain(e: Failure): string {
    if (e.code === 'rate_limited') return copy.ERR.rateLimited(e.retryAfterS ?? 120)
    if (e.code === 'no_finnish') return copy.start.NO_FINNISH_LONG
    if (e.code === 'network') return copy.ERR.network
    if (e.status === 404) return copy.start.INGEST_NOT_FOUND
    return copy.start.LOAD_FAILED
  }

  function show(next: IngestVM) {
    vm = next
    problem = null
    if (next.state === 'done' && next.openHref) {
      alive = false
      router.navigate(next.openHref, { replace: true })
    }
  }

  async function poll() {
    if (!alive) return
    const r = await getIngest(qid)
    if (!alive) return
    now = Date.now()
    if (r.ok) show(r.data)
    else if (r.error.status === 404 && !triedStart) {
      // Opened by link without a running job: start one.
      triedStart = true
      const s = await startIngest(qid)
      if (s.ok) show(s.data)
      else problem = explain(s.error)
    } else problem = explain(r.error)
    if (alive && vm?.state !== 'failed') timer = setTimeout(poll, POLL_MS)
  }

  onMount(() => {
    poll()
    return () => {
      alive = false
      clearTimeout(timer)
    }
  })

  async function faster(e: MouseEvent) {
    e.preventDefault()
    if (!vm?.faster || busy) return
    busy = true
    const r = await startIngest(qid, vm.faster.since)
    busy = false
    if (r.ok) show(r.data)
    else problem = explain(r.error)
  }

  function stateText(e: IngestEdition): string {
    if (e.state === 'done') return copy.start.DONE
    if (e.state === 'running') return copy.start.pct(e.pct)
    if (e.error === 'no_article') return copy.start.NO_ARTICLE
    if (e.state === 'failed') return copy.start.FAILED
    return copy.start.WAITING
  }

  // The one edition worth a notice: slowed down by Wikipedia first, else a real failure (not a missing article).
  const stuck = $derived(
    vm?.editions.find((e) => e.error === 'rate_limited' && e.state !== 'done') ??
      vm?.editions.find((e) => e.state === 'failed' && e.error !== 'no_article') ??
      null,
  )
  const retryInS = $derived(stuck?.retryAt ? Math.max(0, Math.round((Date.parse(stuck.retryAt) - now) / 1000)) : null)
</script>

<Bar right="change" />
<main class="col">
  {#if vm}
    <section class="head">
      <h1 data-testid={TID.ingestTitle}>{vm.title}</h1>
      <p class="sec">{copy.start.READING}</p>
    </section>

    <div class="prog" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={vm.progress} data-testid={TID.ingestProgress}>
      <i style:width="{vm.progress}%"></i>
    </div>
    {#if vm.etaS !== null}<p class="meta" data-testid={TID.ingestEta}>{copy.start.left(vm.etaS)}</p>{/if}

    {#if vm.openHref && vm.state === 'usable'}
      <div class="ready">
        <Button href={vm.openHref} variant="primary" testid={TID.ingestOpen}>{copy.start.compareReady(vm.readyCount)}</Button>
      </div>
    {/if}

    {#if vm.state === 'failed'}
      <div class="gap"><Notice>{copy.start.INGEST_FAILED}</Notice></div>
    {:else if stuck && vm.readyCount > 0}
      <!-- The compare button above already opens the ready editions, so no second link here. -->
      <div class="gap">
        <EditionFailed lang={stuck.lang} rateLimited={stuck.error === 'rate_limited'} othersReady={vm.readyCount} openHref={null} {retryInS} />
      </div>
    {:else if stuck}
      <div class="gap">
        <Notice>{copy.states.editionFailed(stuck.lang, stuck.error === 'rate_limited')}{#if retryInS !== null}. {copy.states.retryingIn(retryInS)}{/if}</Notice>
      </div>
    {/if}
    {#if problem}<div class="gap"><Notice>{problem}</Notice></div>{/if}

    <div class="eds">
      {#each vm.editions as e (e.lang)}
        <div data-testid={TID.ingestEdition} data-lang={e.lang} data-state={e.state}>
          <span>{copy.edition(e.lang)}</span><span class:num={e.state === 'running'} class:muted={e.state === 'waiting' || e.state === 'failed' || e.error === 'no_article'}
            >{stateText(e)}</span
          >
        </div>
      {/each}
    </div>

    {#if vm.faster}
      <a class="alt sec u" href={router.path} data-testid={TID.ingestFaster} aria-disabled={busy} onclick={faster}
        >{copy.start.faster(vm.faster.fromYear, vm.faster.toYear, vm.faster.etaS)}</a
      >
    {/if}
  {:else if problem}
    <div class="head"><Notice>{problem}</Notice></div>
  {/if}

  <Footer />
</main>

<style>
  .head { padding-top: 48px; }
  .head .sec { margin-top: 8px; }
  .prog { margin-top: 40px; height: 4px; border-radius: var(--r-mark); background: var(--line); }
  .prog i { display: block; height: 100%; border-radius: var(--r-mark); background: var(--fg); transition: width 0.4s ease; }
  .meta { margin-top: 12px; }
  .eds { margin-top: 40px; border-top: 1px solid var(--line); }
  .eds div { display: flex; justify-content: space-between; gap: 16px; padding: 12px 0; border-bottom: 1px solid var(--line); }
  .alt { display: inline-block; margin-top: 32px; }
  .ready { display: flex; align-items: center; gap: 16px; margin-top: 24px; }
  .gap { margin-top: 24px; }
  @media (max-width: 600px) {
    .head { padding-top: 32px; }
    .ready { flex-direction: column; align-items: stretch; gap: 8px; }
    .ready :global(.btn) { justify-content: center; }
  }
</style>
