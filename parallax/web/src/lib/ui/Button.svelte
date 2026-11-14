<script lang="ts">
  // wf .btn. With href it is a link, otherwise a <button>. drop = the small chevron after the label.
  import type { Snippet } from 'svelte'
  import Icon from './Icon.svelte'

  let {
    href,
    variant = 'default',
    drop = false,
    icon,
    testid,
    type = 'button',
    disabled = false,
    expanded,
    onclick,
    children,
  }: {
    href?: string
    variant?: 'default' | 'primary' | 'text'
    drop?: boolean
    icon?: 'search' | 'calendar'
    testid?: string
    type?: 'button' | 'submit'
    disabled?: boolean
    expanded?: boolean
    onclick?: (e: MouseEvent) => void
    children: Snippet
  } = $props()
</script>

{#if href}
  <a class="btn {variant === 'default' ? '' : variant}" class:drop {href} data-testid={testid} {onclick}
    >{#if icon}<Icon name={icon} />{/if}{@render children()}</a
  >
{:else}
  <button class="btn {variant === 'default' ? '' : variant}" class:drop {type} {disabled} aria-expanded={expanded} data-testid={testid} {onclick}
    >{#if icon}<Icon name={icon} />{/if}{@render children()}</button
  >
{/if}
