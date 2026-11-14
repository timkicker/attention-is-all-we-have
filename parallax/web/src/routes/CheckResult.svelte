<script lang="ts">
  // STUB by the shell. Owner: P3. Replace the placeholder with the real page.
  import * as copy from '../lib/copy'
  import { getCounts, resolveTopic } from '../lib/data'
  import { dateState } from '../lib/date.svelte'
  import type { TabCounts } from '../lib/model'
  import Bar from '../lib/ui/Bar.svelte'
  import Footer from '../lib/ui/Footer.svelte'
  import TopicHeader from '../lib/ui/TopicHeader.svelte'

  let { params }: { params: Record<string, string> } = $props()
  let counts = $state<TabCounts>({ differences: null, removed: null })
  let title = $state('')
  $effect(() => {
    resolveTopic(params.qid).then((r) => (title = r.ok ? r.data.title : params.qid))
    getCounts(params.qid, dateState.value).then((c) => (counts = c))
  })
</script>

<Bar right="change" />
<main class="col">
  <TopicHeader qid={params.qid} {title} subtitle={copy.check.SUB_CHECK}  active="check" {counts} />
  <p class="stub sec">{copy.STUB}</p>
  <Footer fromQid={params.qid} />
</main>

<style>
  .stub { margin-top: 24px; }
</style>
