<script lang="ts">
  // Under the hood (wf/11). Owner: P4. ?from=qid makes the bar link go back to that topic.
  import * as copy from '../lib/copy'
  import { getHood, resolveTopic } from '../lib/data'
  import type { HoodVM, Result } from '../lib/model'
  import { paths, router } from '../lib/router.svelte'
  import { TID } from '../lib/testids'
  import Bar from '../lib/ui/Bar.svelte'
  import Footer from '../lib/ui/Footer.svelte'

  let { params: _params }: { params: Record<string, string> } = $props()
  const from = $derived(router.query.get('from'))
  let fromTitle = $state('')
  let res = $state<Result<HoodVM> | null>(null)

  $effect(() => {
    const qid = from
    fromTitle = ''
    if (qid) resolveTopic(qid).then((r) => (fromTitle = r.ok ? r.data.title : ''))
  })
  $effect(() => {
    const qid = from
    res = null
    getHood(qid).then((r) => (res = r))
  })

  const vm = $derived(res?.ok ? res.data : null)
  const h = copy.hood
  // Wireframe words in mock mode; live data says what the logged statement really does.
  const queryLead = $derived(router.mock ? h.QUERY_P : h.QUERY_P_LIVE)
</script>

<Bar right={from && fromTitle ? 'back' : 'none'} backTitle={fromTitle} backHref={from ? paths.differences(from) : ''} />
<main class="col">
  <section class="top">
    <h1>{h.TITLE}</h1>
    <p class="sec">{h.SUB}</p>
  </section>

  <section class="s" data-testid={TID.hoodSection} data-section="matched">
    <h2>{h.MATCHED_H}</h2>
    <p>{h.MATCHED_P1}</p>
    <p>{h.MATCHED_P2}</p>
  </section>

  {#if res && !res.ok}
    <section class="s" data-testid={TID.stateError}>
      <p>{copy.ERR.generic}</p>
    </section>
  {/if}

  {#if vm}
    <section class="s" data-testid={TID.hoodSection} data-section="query">
      <h2>{h.QUERY_H}</h2>
      <p>{queryLead}</p>
      <pre data-testid={TID.hoodQuery}>{vm.sql}</pre>
    </section>

    <section class="s" data-testid={TID.hoodSection} data-section="numbers">
      <h2>{h.NUMBERS_H}</h2>
      <dl>
        {#if vm.versions !== null}
          <div data-testid={TID.hoodNumber} data-key="versions"><dt>{h.versionsFor(vm.topicTitle)}</dt><dd>{copy.fmtNum(vm.versions)}</dd></div>
        {/if}
        {#if vm.top1 !== null}
          <div data-testid={TID.hoodNumber} data-key="top1"><dt>{h.TOP1}</dt><dd>{h.recall(vm.top1)}</dd></div>
        {/if}
        {#if vm.top5 !== null}
          <div data-testid={TID.hoodNumber} data-key="top5"><dt>{h.TOP5}</dt><dd>{h.recall(vm.top5)}</dd></div>
        {/if}
        {#if vm.judgeAccuracy != null}
          <div data-testid={TID.hoodNumber} data-key="judge"><dt>{h.judgeAgreement(vm.judgeN)}</dt><dd>{h.share(vm.judgeAccuracy)}</dd></div>
        {/if}
        {#if vm.embedRate != null}
          <div data-testid={TID.hoodNumber} data-key="embed_rate"><dt>{h.embedRate(vm.embedGpu)}</dt><dd>{h.perSecond(vm.embedRate)}</dd></div>
        {/if}
        {#if vm.queryMs !== null}
          <div data-testid={TID.hoodNumber} data-key="query_ms"><dt>{h.QUERY_MS}</dt><dd>{h.ms(vm.queryMs)}</dd></div>
        {/if}
      </dl>
    </section>

    <section class="s" data-testid={TID.hoodSection} data-section="limits">
      <h2>{h.LIMITS_H}</h2>
      <p>{h.LIMIT_TRANSLATION}</p>
      {#if vm.top1 !== null}<p>{h.limitRecall(vm.top1)}</p>{/if}
      <p>{h.LIMIT_SCOPE}</p>
    </section>
  {/if}
  <Footer variant="short" />
</main>

<style>
  .top { padding-top: 24px; }
  .top p { margin-top: 4px; }
  section.s { margin-top: 56px; }
  section.s p { margin-top: 8px; color: var(--fg2); }
  pre { margin-top: 16px; padding: 16px; background: var(--soft); border-radius: var(--r); font: 400 var(--fs-13) / var(--lh-13) var(--mono); overflow-x: auto; white-space: pre; font-variant-ligatures: none; }
  dl { margin-top: 8px; }
  dl div { display: flex; justify-content: space-between; gap: 16px; padding: 12px 0; border-bottom: 1px solid var(--line); }
  dt { color: var(--fg2); }
  dd { white-space: nowrap; }
  @media (max-width: 600px) {
    section.s { margin-top: 48px; }
  }
</style>
