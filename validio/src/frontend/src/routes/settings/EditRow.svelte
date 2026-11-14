<script lang="ts">
  /// A Settings row: the label, the value, and Change. Change opens the row's
  /// own small form under it; a row without `onchange` is read only.
  import type { Snippet } from "svelte";
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import { ListRow } from "$lib/v2";

  let {
    id,
    label,
    value,
    description,
    open = false,
    onchange,
    children,
  }: {
    id: string;
    label: string;
    value: string;
    description?: string;
    open?: boolean;
    onchange?: () => void;
    /** The form, shown while `open`. */
    children?: Snippet;
  } = $props();
</script>

<ListRow id="row-{id}" {label} {description} below={open ? children : undefined}>
  {#snippet control()}
    <span class="er">
      <span class="er-value" data-testid="{id}-value">{value}</span>
      {#if onchange && !open}
        <Button variant="outline" size="sm" id="{id}-change" data-testid="{id}-change" aria-label="Change {label.toLowerCase()}" onclick={onchange}>Change</Button>
      {/if}
    </span>
  {/snippet}
</ListRow>

<style>
  .er {
    display: inline-flex;
    align-items: center;
    justify-content: flex-end;
    gap: 12px;
  }
  .er-value {
    min-width: 0;
    /* Breaks inside a word only when the word alone is wider than the row:
       a 6-digit code never splits. */
    overflow-wrap: break-word;
    text-align: right;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    font-weight: 500;
    color: var(--v-fg);
  }
</style>
