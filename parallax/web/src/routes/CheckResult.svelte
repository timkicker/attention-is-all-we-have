<script lang="ts">
  // Check result (wf/10): which editions back each statement of the answer.
  import * as copy from '../lib/copy'
  import { getCheckRun, resolveTopic } from '../lib/data'
  import { dateState } from '../lib/date.svelte'
  import type { CheckResultVM, Result, TabCounts } from '../lib/model'
  import { TID } from '../lib/testids'
  import Bar from '../lib/ui/Bar.svelte'
  import Footer from '../lib/ui/Footer.svelte'
  import Item from '../lib/ui/Item.svelte'
  import Skeleton from '../lib/ui/states/Skeleton.svelte'
  import TopicHeader from '../lib/ui/TopicHeader.svelte'

  let { params }: { params: Record<string, string> } = $props()

  let res = $state<Result<CheckResultVM> | null>(null)
  let title = $state('')
  let counts = $state<TabCounts>({ differences: null, removed: null })
  let whole = $state(false)
  // The first FIRST rows, then all of them after "Show N more".
  const FIRST = 6
  let all = $state(false)

  $effect(() => {
    resolveTopic(params.qid).then((r) => (title = r.ok ? r.data.title : params.qid))
  })
  $effect(() => {
    const date = dateState.value
    let live = true
    getCheckRun(params.qid, date, params.runId).then((r) => {
      if (!live) return
      res = r
      if (r.ok) {
        counts = r.data.counts
        title = r.data.topic.title
      }
    })
    return () => (live = false)
  })
</script>

<Bar right="change" />
<main class="col">
  <TopicHeader qid={params.qid} {title} subtitle={copy.check.SUB_CHECK} active="check" {counts} />

  {#if res === null}
    <Skeleton />
  {:else if !res.ok}
    <p class="msg sec" role="alert">{res.error.status === 404 ? copy.ERR.notFound : res.error.code === 'network' ? copy.ERR.network : copy.ERR.generic}</p>
  {:else}
    {@const vm = res.data}
    <div class="meta" data-testid={TID.checkMeta}>
      <p class="sec">
        {#if vm.label && vm.recordedOn}{vm.label},{' '}<span class="nw">{copy.check.recordedDate(vm.recordedOn)}</span>{:else}{vm.label ?? copy.check.PASTED}{/if}
      </p>
      <a class="u sec" href={vm.againHref} data-testid={TID.checkAgain}>{copy.check.CHECK_ANOTHER}</a>
    </div>
    <p class="ans sec">
      <span class="serif" data-testid={TID.checkAnswer}>{copy.quote(whole ? vm.answer : vm.excerpt)}</span>
      {#if vm.excerpt !== vm.answer}
        <button type="button" class="u" aria-expanded={whole} data-testid={TID.checkWhole} onclick={() => (whole = !whole)}>{whole ? copy.check.SHOW_LESS : copy.check.SHOW_WHOLE}</button>
      {/if}
    </p>
    <p class="sum t18" data-testid={TID.checkSummary}>{copy.checkSummary(vm.summary, vm.mostBacked)}</p>

    <div class="list">
      {#each all ? vm.rows : vm.rows.slice(0, FIRST) as row (row.id)}
        <Item href={row.href} testid={TID.checkRow} data-verdict={row.verdict}>
          <p class="v parts" class:bad={row.verdict !== 'backed'}>{#each row.head as h, k (k)}<span>{h}</span>{/each}</p>
          <p class="say">{row.say}</p>
        </Item>
      {/each}
    </div>
    {#if !all && vm.rows.length > FIRST}
      <p class="more"><button class="btn" type="button" data-testid={TID.showMore} onclick={() => (all = true)}>{copy.showMore(vm.rows.length - FIRST)}</button></p>
    {/if}
  {/if}

  <Footer fromQid={params.qid} />
</main>

<style>
  .more { margin-top: 24px; }
  .meta { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-top: 24px; }
  .meta a, .nw { flex: none; white-space: nowrap; }
  .v { color: var(--fg2); }
  .v.bad { color: var(--fg); font-weight: var(--w-medium); }
  .ans { margin-top: 16px; }
  .ans button { color: inherit; font: inherit; }
  .sum { margin-top: 24px; }
  .list { margin-top: 16px; }
  .list :global(.item .say) { margin-top: 4px; }
  .msg { padding: 40px 0 48px; }
  @media (max-width: 600px) {
    .meta { flex-direction: column; align-items: flex-start; gap: 4px; }
  }
</style>
