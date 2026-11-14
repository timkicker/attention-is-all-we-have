<script lang="ts">
  // The result popover under the start search (wf 02): title, status right, description below.
  import * as copy from '../copy'
  import type { SearchResult } from '../model'
  import { TID } from '../testids'

  let {
    results,
    active,
    searching,
    failed,
    onchoose,
    onhover,
  }: {
    results: SearchResult[]
    active: number
    searching: boolean
    failed: string | null
    onchoose: (r: SearchResult) => void
    onhover: (i: number) => void
  } = $props()

  function status(r: SearchResult): string {
    if (r.status === 'ready') return copy.start.READY
    if (r.status === 'loading') return copy.start.LOADING
    if (r.status === 'no_finnish') return copy.start.NO_FINNISH
    return r.etaS !== null ? copy.start.toLoad(r.etaS) : ''
  }

  function click(e: MouseEvent, r: SearchResult) {
    e.preventDefault()
    onchoose(r)
  }
</script>

<div class="pop res" role="listbox" aria-label={copy.start.SEARCH_LABEL} data-testid={TID.startResults}>
  {#each results as r, i (r.qid)}
    {#if r.href}
      <a
        href={r.href}
        role="option"
        aria-selected={i === active}
        class:on={i === active}
        data-testid={TID.startResult}
        data-status={r.status}
        onclick={(e) => click(e, r)}
        onmouseenter={() => onhover(i)}
        ><span class="tt">{r.title}</span><span class="s" class:muted={r.status !== 'ready'}>{status(r)}</span><span class="d t13 muted"
          >{r.description}</span
        ></a
      >
    {:else}
      <div role="option" aria-selected={i === active} aria-disabled="true" class="off" class:on={i === active} data-testid={TID.startResult} data-status={r.status}>
        <span class="tt">{r.title}</span><span class="s muted">{status(r)}</span><span class="d t13 muted">{r.description}</span>
      </div>
    {/if}
  {/each}
  {#if failed}
    <p class="msg sec">{failed}</p>
  {:else if !results.length}
    <p class="msg muted">{searching ? copy.start.SEARCHING : copy.start.NO_RESULTS}</p>
  {/if}
</div>

<style>
  .res { position: absolute; left: 0; right: 0; top: 64px; z-index: 2; padding: 8px; }
  .res a, .res .off { display: grid; grid-template-columns: minmax(0, 1fr) auto; grid-template-areas: "tt s" "d d"; column-gap: 12px; align-items: baseline; padding: 8px 12px; border-radius: var(--r); }
  .res .on { background: var(--soft); }
  .res .off .tt { color: var(--fg2); }
  .res .tt { grid-area: tt; }
  .res .d { grid-area: d; }
  .res .s { grid-area: s; font-size: var(--fs-13); line-height: var(--lh-13); white-space: nowrap; }
  .msg { padding: 8px 12px; }
  @media (max-width: 600px) { .res a, .res .off { grid-template-areas: "tt tt" "d s"; } }
</style>
