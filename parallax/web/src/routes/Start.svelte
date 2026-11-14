<script lang="ts">
  // STUB by the shell. Owner: P1. Replace the placeholder with the real page.
  import * as copy from '../lib/copy'
  import Bar from '../lib/ui/Bar.svelte'
  import Footer from '../lib/ui/Footer.svelte'

  let { params }: { params: Record<string, string> } = $props()
</script>

<Bar right="none" />
<main class="wide">
  <p class="stub sec" data-params={JSON.stringify(params)}>{copy.STUB}</p>
  <Footer />
</main>

<style>
  .stub { padding-top: 48px; }
</style>
