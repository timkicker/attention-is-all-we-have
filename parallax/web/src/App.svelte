<script lang="ts">
  // Route table: one page component per route. Owned by the shell; pages own their files.
  import { onMount } from 'svelte'
  import * as copy from './lib/copy'
  import { dateState } from './lib/date.svelte'
  import { installLinkHandler, router } from './lib/router.svelte'
  import Bar from './lib/ui/Bar.svelte'
  import Footer from './lib/ui/Footer.svelte'
  import Check from './routes/Check.svelte'
  import CheckResult from './routes/CheckResult.svelte'
  import DevStates from './routes/DevStates.svelte'
  import Differences from './routes/Differences.svelte'
  import Hood from './routes/Hood.svelte'
  import Ingest from './routes/Ingest.svelte'
  import Removed from './routes/Removed.svelte'
  import Start from './routes/Start.svelte'
  import Statement from './routes/Statement.svelte'

  onMount(installLinkHandler)

  // A ?date= that is no past day (a typo, a future day) shows the newest version; the address then says so too,
  // instead of keeping a date the page does not show.
  $effect(() => {
    if (router.query.has('date') && dateState.value === null) router.setQuery({ date: null }, { replace: true })
  })

  const PAGES = { start: Start, ingest: Ingest, differences: Differences, statement: Statement, removed: Removed, check: Check, checkRun: CheckResult, hood: Hood, devStates: DevStates }
  const m = $derived(router.current)
  const Page = $derived(m.name === 'notFound' ? null : PAGES[m.name])
</script>

{#if Page}
  {#key m.name + JSON.stringify(m.params)}
    <Page params={m.params} />
  {/key}
{:else}
  <Bar />
  <main class="col">
    <h1 class="nf">{copy.ERR.notFound}</h1>
    <Footer />
  </main>
{/if}

<style>
  .nf { padding-top: 48px; }
</style>
