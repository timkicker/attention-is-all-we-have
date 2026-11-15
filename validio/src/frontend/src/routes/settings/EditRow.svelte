<script lang="ts">
  /// A Settings row: the label, the value, and Change. Change opens the row's
  /// own small form under it; a row without `onchange` is read only.
  import type { Snippet } from "svelte";
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import { Check } from "@lucide/svelte";
  import { ListRow } from "$lib/v2";
  import { blurSwap } from "$lib/motion";

  let {
    id,
    label,
    value,
    description,
    open = false,
    saved = false,
    onchange,
    children,
  }: {
    id: string;
    label: string;
    value: string;
    description?: string;
    open?: boolean;
    /** Just saved: the value glows once and a check stands beside it (plans/016). */
    saved?: boolean;
    onchange?: () => void;
    /** The form, shown while `open`. */
    children?: Snippet;
  } = $props();
</script>

<ListRow id="row-{id}" {label} {description} below={open ? children : undefined}>
  {#snippet control()}
    <span class="er">
      {#if saved}<span class="er-ok" in:blurSwap aria-hidden="true"><Check size={14} strokeWidth={2.25} /></span>{/if}
      {#key value}<span class="er-value" class:v-glow={saved} data-testid="{id}-value">{value}</span>{/key}
      {#if onchange && !open}
        <span class="er-btn" in:blurSwap={{ duration: 160 }}>
          <Button variant="outline" size="sm" id="{id}-change" data-testid="{id}-change" aria-label="Change {label.toLowerCase()}" onclick={onchange}>Change</Button>
        </span>
      {/if}
    </span>
  {/snippet}
</ListRow>

<style>
  .er-ok {
    display: inline-flex;
    color: var(--v-ok-text);
  }
  .er-btn {
    display: inline-flex;
  }
  .er-value {
    padding: 0 2px;
    border-radius: var(--radius-chip);
  }
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
