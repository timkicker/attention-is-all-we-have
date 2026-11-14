<script lang="ts">
  // "As of today" button (wf/05) that opens a .pop: quick picks plus a typed date (YYYY-MM-DD).
  // Reads and writes the shared date state (?date=), so every tab follows. Escape and an outside
  // click close it; focus goes back to the button.
  import * as copy from '../copy'
  import { dateState } from '../date.svelte'
  import { isIsoDate } from '../format'
  import { TID } from '../testids'
  import Icon from './Icon.svelte'

  /** Quick picks, newest first; null = the latest stored version. latest = YYYY-MM-DD of the newest stored revision
   *  (the data is not refreshed after a load, so without a date the button names that day instead of "today"). */
  let {
    picks = [null, '2020-01-01', '2015-01-01', '2010-01-01', '2008-01-01'],
    latest = null,
  }: { picks?: (string | null)[]; latest?: string | null } = $props()

  let open = $state(false)
  let typed = $state('')
  let bad = $state(false)
  let root: HTMLElement
  let button: HTMLButtonElement

  function close(focus = true) {
    open = false
    bad = false
    if (focus) button?.focus()
  }
  function choose(d: string | null) {
    dateState.set(d)
    close()
  }
  function apply(e: SubmitEvent) {
    e.preventDefault()
    if (!isIsoDate(typed.trim())) {
      bad = true
      return
    }
    choose(typed.trim())
  }
  function onDoc(e: MouseEvent) {
    if (open && root && !root.contains(e.target as Node)) close(false)
  }
  function onKey(e: KeyboardEvent) {
    if (open && e.key === 'Escape') close()
  }
</script>

<svelte:document onclick={onDoc} onkeydown={onKey} />

<div class="asof" bind:this={root}>
  <button
    bind:this={button}
    class="btn drop"
    type="button"
    aria-haspopup="dialog"
    aria-expanded={open}
    data-testid={TID.asOf}
    onclick={() => {
      open = !open
      typed = dateState.value ?? ''
    }}><Icon name="calendar" />{copy.asOf(dateState.value, latest)}</button
  >
  {#if open}
    <div class="pop panel" role="dialog" aria-label={copy.DATE_LABEL} data-testid={TID.asOfPop}>
      <ul>
        {#each picks as p (p)}
          <li>
            <button type="button" class="pick" class:on={p === dateState.value} data-testid={TID.asOfPick} onclick={() => choose(p)}
              >{p ? copy.fmtDate(p) : latest ? copy.asOf(null, latest) : copy.TODAY}</button
            >
          </li>
        {/each}
      </ul>
      <form onsubmit={apply}>
        <label class="t13 sec" for="asof-input">{copy.DATE_LABEL}</label>
        <div class="row">
          <input
            id="asof-input"
            class="field"
            inputmode="numeric"
            placeholder={copy.DATE_PLACEHOLDER}
            bind:value={typed}
            aria-invalid={bad}
            data-testid={TID.asOfInput}
          />
          <button class="btn" type="submit" data-testid={TID.asOfApply}>{copy.DATE_SHOW}</button>
        </div>
        {#if bad}<p class="t13 sec" role="alert">{copy.DATE_INVALID}</p>{/if}
      </form>
    </div>
  {/if}
</div>

<style>
  .asof { position: relative; flex: none; }
  .panel { position: absolute; right: 0; top: calc(var(--control) + 8px); z-index: 3; width: 280px; padding: 8px; }
  ul { list-style: none; }
  .pick { display: block; width: 100%; text-align: left; padding: 8px 12px; border-radius: var(--r); }
  .pick:hover, .pick.on { background: var(--soft); }
  form { border-top: 1px solid var(--line); margin-top: 4px; padding: 12px 12px 4px; }
  .row { display: flex; gap: 8px; margin-top: 4px; }
  .row .field { flex: 1 1 auto; min-width: 0; color: var(--fg); outline: none; }
  .row .field:focus { border-color: var(--fg); }
  p { margin-top: 4px; }
</style>
