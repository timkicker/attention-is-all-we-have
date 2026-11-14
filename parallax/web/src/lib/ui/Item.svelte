<script lang="ts">
  // wf .item: one hairline row. With href it is a link and gets the chevron. on = selected (soft ground).
  import type { Snippet } from 'svelte'

  let { href, on = false, testid, children, ...rest }: { href?: string | null; on?: boolean; testid?: string; children: Snippet; [k: string]: unknown } =
    $props()
</script>

{#if href}
  <a class="item" class:on {href} data-testid={testid} {...rest}>{@render children()}</a>
{:else}
  <div class="item" class:on data-testid={testid} {...rest}>{@render children()}</div>
{/if}
