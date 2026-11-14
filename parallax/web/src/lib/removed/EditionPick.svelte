<script lang="ts">
  // "Any edition" button (wf/08) with a .pop list: any edition, then each edition that removed something.
  // Escape and an outside click close it; focus goes back to the button.
  import * as copy from '../copy'
  import type { Lang } from '../model'
  import { TID } from '../testids'

  let { value, editions, onpick }: { value: Lang | null; editions: Lang[]; onpick: (lang: Lang | null) => void } = $props()

  let open = $state(false)
  let root: HTMLElement
  let button: HTMLButtonElement

  function close(focus = true) {
    open = false
    if (focus) button?.focus()
  }
  function choose(l: Lang | null) {
    onpick(l)
    close()
  }
  function onDoc(e: MouseEvent) {
    if (open && root && !root.contains(e.target as Node)) close(false)
  }
  function onKey(e: KeyboardEvent) {
    if (open && e.key === 'Escape') close()
  }
</script>

<svelte:document onclick={onDoc} onkeydown={onKey} />

<div class="ed" bind:this={root}>
  <button
    bind:this={button}
    class="btn drop"
    type="button"
    aria-haspopup="listbox"
    aria-expanded={open}
    aria-label={copy.removed.EDITION_FILTER_LABEL}
    data-testid={TID.removedEdition}
    onclick={() => (open = !open)}>{value ? copy.edition(value) : copy.removed.ANY_EDITION}</button
  >
  {#if open}
    <ul class="pop panel" role="listbox" aria-label={copy.removed.EDITION_FILTER_LABEL} data-testid={TID.removedEditionPop}>
      {#each [null, ...editions] as l (l ?? 'any')}
        <li role="option" aria-selected={l === value}>
          <button type="button" class="pick" class:on={l === value} onclick={() => choose(l)}>{l ? copy.edition(l) : copy.removed.ANY_EDITION}</button>
        </li>
      {/each}
    </ul>
  {/if}
</div>

<style>
  .ed { position: relative; flex: none; }
  .panel { position: absolute; left: 0; top: calc(var(--control) + 8px); z-index: 3; width: 200px; padding: 8px; list-style: none; }
  .pick { display: block; width: 100%; text-align: left; padding: 8px 12px; border-radius: var(--r); }
  .pick:hover, .pick.on { background: var(--soft); }
</style>
