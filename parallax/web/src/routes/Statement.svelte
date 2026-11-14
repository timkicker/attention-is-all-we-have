<script lang="ts">
  // One statement (wf/06): how each edition tells it, grouped by wording, and when editions changed it.
  import * as copy from '../lib/copy'
  import type { Change, Group } from '../lib/adapt/topic'
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
  function originals(g: Group | StatementVM['groups'][number]): { lang: Lang; say: MarkedText }[] {
    const m = (g as Group).marked
    if (m?.length) return m
    return g.originals.map((o) => ({ lang: o.lang, say: { text: o.text, spans: [] } }))
  }
  const open = $derived(((vm as { open?: Lang[] } | null)?.open ?? []) as Lang[])
  const changeLine = (c: StatementVM['changes'][number]) =>
    copy.topic.changedFromToAt(c.date, (c as Change).approx ?? false, c.lang, c.from, c.to)
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
                <p class="ed">{copy.edition(o.lang)}</p>
                <p class="say">{#if o.say.text}<Marked value={o.say} />{/if}</p>
              </div>
            {/each}
          {:else}
            <p class="ed">{copy.editions(g.langs)}</p>
            <p class="say"><Marked value={g.say} /></p>
          {/if}
        </div>
      {/each}
      {#if vm.missing.length}
        <div class="item" data-testid={TID.statementMissing}><p class="muted">{copy.notIn(vm.missing)}</p></div>
      {/if}
      {#if open.length}
        <div class="item"><p class="muted">{copy.topic.notCompared(open)}</p></div>
      {/if}
    </div>

    <section class="changed">
      <h2>{copy.topic.WHEN_IT_CHANGED}</h2>
      <div class="list">
        {#each vm.changes as c, i (i)}
          <div class="item" data-testid={TID.changeRow}>
            <p>{changeLine(c)}</p>
            {#if c.comment}<p class="t13 muted">{copy.editComment(c.comment)}</p>{/if}
          </div>
        {:else}
          <div class="item"><p class="muted">{copy.topic.NO_CHANGES}</p></div>
        {/each}
      </div>
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
  .changed { margin-top: 64px; }
  .changed .item { padding: 16px 0; }
</style>
