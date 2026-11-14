<script lang="ts">
  // Topic header from wf/05: h1, subtitle (optional marked word at its end), three tabs with counts.
  // Tabs keep ?date because paths carry it.
  import * as copy from '../copy'
  import type { TabCounts } from '../model'
  import { paths } from '../router.svelte'
  import { TID } from '../testids'

  let {
    qid,
    title,
    subtitle,
    mark = '',
    active,
    counts = { differences: null, removed: null },
  }: {
    qid: string
    title: string
    subtitle: string
    mark?: string
    active: copy.TabKey
    counts?: TabCounts
  } = $props()
</script>

<section class="thead">
  <h1 data-testid={TID.topicTitle}>{title}</h1>
  <p class="sub sec">{subtitle}{#if mark}{' '}<mark>{mark}</mark>{/if}</p>
  <nav class="tabs">
    <a class:on={active === 'differences'} aria-current={active === 'differences' ? 'page' : undefined} href={paths.differences(qid)} data-testid={TID.tabDifferences}
      >{copy.TABS.differences}{#if counts.differences !== null}{' '}<span class="muted">{copy.fmtNum(counts.differences)}</span>{/if}</a
    >
    <a class:on={active === 'removed'} aria-current={active === 'removed' ? 'page' : undefined} href={paths.removed(qid)} data-testid={TID.tabRemoved}
      >{copy.TABS.removed}{#if counts.removed !== null}{' '}<span class="muted">{copy.fmtNum(counts.removed)}</span>{/if}</a
    >
    <a class:on={active === 'check'} aria-current={active === 'check' ? 'page' : undefined} href={paths.check(qid)} data-testid={TID.tabCheck}>{copy.TABS.check}</a>
  </nav>
</section>

<style>
  .sub { margin-top: 4px; }
</style>
