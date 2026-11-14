<script lang="ts">
  // App bar: wordmark left, at most one quiet link right.
  // right: 'none' (start page), 'change' (Change article, topic pages), 'hood' (Under the hood),
  // 'back' (Back to <backTitle>, Under the hood page; needs backHref).
  import * as copy from '../copy'
  import { paths } from '../router.svelte'
  import { TID } from '../testids'
  import Icon from './Icon.svelte'

  let {
    right = 'none',
    backTitle = '',
    backHref = '',
  }: { right?: 'none' | 'change' | 'hood' | 'back'; backTitle?: string; backHref?: string } = $props()
</script>

<header class="bar" data-testid={TID.bar}>
  <div class="wide in">
    <a class="logo" href={paths.start()} data-testid={TID.barLogo}>{copy.WORDMARK}</a>
    {#if right !== 'none'}
      <span class="sp"></span>
      {#if right === 'change'}
        <a class="link" href={paths.start()} data-testid={TID.barLink}><Icon name="search" />{copy.CHANGE_ARTICLE}</a>
      {:else if right === 'hood'}
        <a class="link" href={paths.hood()} data-testid={TID.barLink}>{copy.UNDER_THE_HOOD}</a>
      {:else}
        <a class="link" href={backHref} data-testid={TID.barLink}>{copy.backTo(backTitle)}</a>
      {/if}
    {/if}
  </div>
</header>
