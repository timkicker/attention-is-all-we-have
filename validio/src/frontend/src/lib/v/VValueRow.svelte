<script lang="ts">
  /// One value row: label in a 184 px cell, the value on the page's value
  /// column, a muted sub under it. A row with `href` or `onclick` is one link.
  import type { Snippet } from "svelte";
  import { ChevronRight } from "@lucide/svelte";

  let {
    label,
    value,
    sub,
    testid,
    href,
    onclick,
    children,
  }: {
    label: string;
    value?: string;
    sub?: string;
    testid?: string;
    href?: string;
    onclick?: (e: MouseEvent) => void;
    children?: Snippet;
  } = $props();
</script>

{#snippet body()}
  <span class="vr-label">{label}</span>
  <span class="vr-val">
    <span class="vr-value" data-value>{#if children}{@render children()}{:else}{value}{/if}</span>
    {#if sub}<span class="vr-sub">{sub}</span>{/if}
  </span>
  {#if href || onclick}<ChevronRight class="vr-go" aria-hidden="true" size={16} strokeWidth={1.75} />{/if}
{/snippet}

{#if href || onclick}
  <a class="vr link" {href} {onclick} data-testid={testid} id={testid}>{@render body()}</a>
{:else}
  <div class="vr" data-testid={testid} id={testid}>{@render body()}</div>
{/if}

<style>
  .vr {
    display: grid;
    grid-template-columns: 184px minmax(0, 1fr) auto;
    align-items: start;
    min-height: 56px;
    padding: 12px 16px;
    color: inherit;
    text-decoration: none;
  }
  .vr-label {
    font-size: var(--fs-body);
    line-height: var(--lh-body);
    color: var(--v-fg);
  }
  .vr-val {
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 0;
  }
  .vr-value {
    font-size: var(--fs-body);
    line-height: var(--lh-body);
    font-weight: 500;
    color: var(--v-fg);
    font-variant-numeric: tabular-nums;
  }
  .vr-sub {
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-muted);
  }
  .vr :global(.vr-go) {
    color: var(--v-faint);
    align-self: center;
  }
  a.vr:hover .vr-value {
    text-decoration: underline;
    text-decoration-color: var(--v-faint);
    text-underline-offset: 3px;
  }
  @media (max-width: 760px) {
    .vr {
      grid-template-columns: minmax(0, 1fr) auto;
      row-gap: 4px;
    }
    .vr-label {
      font-size: 14px;
      line-height: 20px;
      grid-column: 1;
    }
    .vr-val {
      grid-column: 1;
    }
    .vr :global(.vr-go) {
      grid-column: 2;
      grid-row: 1 / span 2;
    }
  }
</style>
