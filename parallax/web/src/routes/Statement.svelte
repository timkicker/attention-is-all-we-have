<script lang="ts">
  // STUB by the shell. Owner: P2. Replace the placeholder with the real page.
  import * as copy from '../lib/copy'
  import Bar from '../lib/ui/Bar.svelte'
  import Footer from '../lib/ui/Footer.svelte'

  let { params }: { params: Record<string, string> } = $props()
</script>

<Bar right="change" />
<main class="col">
  <p class="stub sec" data-params={JSON.stringify(params)}>{copy.STUB}</p>
  <Footer />
</main>

<style>
  .stub { padding-top: 48px; }
</style>
