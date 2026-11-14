<script lang="ts">
  // STUB by the shell. Owner: P4. Replace the placeholder with the real page.
  import * as copy from '../lib/copy'
  import { resolveTopic } from '../lib/data'
  import { paths, router } from '../lib/router.svelte'
  import Bar from '../lib/ui/Bar.svelte'
  import Footer from '../lib/ui/Footer.svelte'

  let { params }: { params: Record<string, string> } = $props()
  const from = $derived(router.query.get('from'))
  let fromTitle = $state('')
  $effect(() => {
    if (from) resolveTopic(from).then((r) => (fromTitle = r.ok ? r.data.title : ''))
  })
</script>

<Bar right={from && fromTitle ? 'back' : 'none'} backTitle={fromTitle} backHref={from ? paths.differences(from) : ''} />
<main class="col">
  <section class="top">
    <h1>{copy.hood.TITLE}</h1>
    <p class="sec">{copy.hood.SUB}</p>
  </section>
  <p class="stub sec" data-params={JSON.stringify(params)}>{copy.STUB}</p>
  <Footer variant="short" />
</main>

<style>
  .top { padding-top: 24px; }
  .top p { margin-top: 4px; }
  .stub { margin-top: 56px; }
</style>
