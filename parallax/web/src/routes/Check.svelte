<script lang="ts">
  // Check an AI answer (wf/09): paste an answer, or open a recorded one. "Check answer" posts it and
  // opens the result at /t/:qid/check/:runId.
  import * as copy from '../lib/copy'
  import { getCheckRecorded, resolveTopic, runCheck } from '../lib/data'
  import { dateState } from '../lib/date.svelte'
  import type { CheckVM, Result, TabCounts } from '../lib/model'
  import { paths, router } from '../lib/router.svelte'
  import { TID } from '../lib/testids'
  import Bar from '../lib/ui/Bar.svelte'
  import Footer from '../lib/ui/Footer.svelte'
  import TopicHeader from '../lib/ui/TopicHeader.svelte'

  let { params }: { params: Record<string, string> } = $props()

  const MAX = 6000
  let res = $state<Result<CheckVM> | null>(null)
  let title = $state('')
  let counts = $state<TabCounts>({ differences: null, removed: null })
  let text = $state('')
  let busy = $state(false)
  let problem = $state('')

  $effect(() => {
    resolveTopic(params.qid).then((r) => (title = r.ok ? r.data.title : params.qid))
  })
  $effect(() => {
    const date = dateState.value
    let live = true
    getCheckRecorded(params.qid, date).then((r) => {
      if (!live) return
      res = r
      if (r.ok) {
        counts = r.data.counts
        title = r.data.topic.title
      }
    })
    return () => (live = false)
  })

  async function submit(e: SubmitEvent) {
    e.preventDefault()
    const t = text.trim()
    if (!t) return void (problem = copy.check.EMPTY_ANSWER)
    if (t.length > MAX) return void (problem = copy.check.TOO_LONG)
    problem = ''
    busy = true
    const r = await runCheck(params.qid, dateState.value, t)
    busy = false
    if (r.ok) router.navigate(paths.checkRun(params.qid, r.data.runId))
    else if (r.error.code === 'empty_text') problem = copy.check.EMPTY_ANSWER
    else if (r.error.code === 'text_too_long') problem = copy.check.TOO_LONG
    else if (r.error.code === 'too_many') problem = copy.ERR.tooMany(r.error.retryAfterS ?? 60)
    else if (r.error.code === 'model_unavailable' || r.error.code === 'embed_unavailable') problem = copy.ERR.modelUnavailable
    else problem = r.error.code === 'network' ? copy.ERR.network : copy.ERR.generic
  }
</script>

<Bar right="change" />
<main class="col">
  <TopicHeader qid={params.qid} {title} subtitle={copy.check.SUB_CHECK} active="check" {counts} />

  <form onsubmit={submit}>
    <textarea
      class="ta"
      bind:value={text}
      placeholder={title ? copy.check.placeholder(title) : ''}
      aria-label={copy.check.ANSWER_LABEL}
      aria-invalid={problem ? true : undefined}
      data-testid={TID.checkInput}
    ></textarea>
    {#if problem}<p class="t13 sec bad" role="alert">{problem}</p>{/if}
    <div class="go">
      {#if res?.ok && res.data.recorded.length}
        <p class="muted parts">
          <span>{copy.check.RECORDED_LEAD}</span>
          {#each res.data.recorded as r (r.runId)}<a class="u" href={r.href} data-testid={TID.checkRecorded}>{r.label}</a>{/each}
        </p>
      {:else}
        <span></span>
      {/if}
      <button class="btn primary" type="submit" disabled={busy} aria-busy={busy} data-testid={TID.checkSubmit}>{busy ? copy.check.CHECKING : copy.check.CHECK_ANSWER}</button>
    </div>
  </form>

  <Footer fromQid={params.qid} />
</main>

<style>
  .ta { display: block; width: 100%; height: 160px; margin-top: 32px; padding: 12px 16px; border: 1px solid var(--line2); border-radius: var(--r); font: 400 var(--fs-15)/24px var(--sans); color: var(--fg); resize: vertical; background: var(--bg); }
  .ta::placeholder { color: var(--fg3); }
  .ta:focus { outline: none; border-color: var(--fg); }
  .bad { margin-top: 8px; }
  .go { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-top: 16px; }
  .go .btn { flex-shrink: 0; margin-left: auto; }
  .go .u { color: var(--fg2); }
  @media (max-width: 600px) {
    .go { flex-direction: column; align-items: stretch; }
    .go .btn { justify-content: center; margin-left: 0; width: 100%; }
  }
</style>
