<script lang="ts">
  // Search field (wf .field): icon + real input. big = the 56px start search.
  // placeholderShort replaces the placeholder at phone width ("Find a statement" -> "Search").
  import { onMount } from 'svelte'
  import Icon from './Icon.svelte'

  let {
    value = $bindable(''),
    placeholder,
    placeholderShort = '',
    label = '',
    big = false,
    testid,
    autofocus = false,
    oninput,
    onkeydown,
    onfocus,
    onblur,
    input = $bindable(),
  }: {
    value?: string
    placeholder: string
    placeholderShort?: string
    label?: string
    big?: boolean
    testid: string
    autofocus?: boolean
    oninput?: (value: string) => void
    onkeydown?: (e: KeyboardEvent) => void
    onfocus?: () => void
    onblur?: () => void
    input?: HTMLInputElement
  } = $props()

  let phone = $state(false)
  onMount(() => {
    const mq = matchMedia('(max-width: 600px)')
    phone = mq.matches
    const on = () => (phone = mq.matches)
    mq.addEventListener('change', on)
    if (autofocus) input?.focus()
    return () => mq.removeEventListener('change', on)
  })
</script>

<label class="field" class:big>
  <Icon name="search" />
  <input
    bind:this={input}
    bind:value
    type="search"
    autocomplete="off"
    spellcheck="false"
    placeholder={phone && placeholderShort ? placeholderShort : placeholder}
    aria-label={label || placeholder}
    data-testid={testid}
    oninput={() => oninput?.(value)}
    {onkeydown}
    {onfocus}
    {onblur}
  />
</label>

<style>
  input[type='search']::-webkit-search-cancel-button { appearance: none; }
</style>
