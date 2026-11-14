<script lang="ts">
  /// A label and value row for Rules, Agent and Settings: the kit Row as is
  /// (label, optional description, the control or value on the right, a full
  /// width `below`). Use inside a ListSection.
  import type { Snippet } from "svelte";
  import { Row } from "@arlen/ui-kit/components/ui/row";

  let {
    id,
    label,
    description,
    value,
    control,
    below,
  }: {
    id?: string;
    label: string;
    description?: string;
    /** Plain text on the right; `control` wins when both are set. */
    value?: string;
    control?: Snippet;
    below?: Snippet;
  } = $props();
</script>

{#snippet plain()}<span class="lr-value" data-testid={id ? `${id}-value` : undefined}>{value}</span>{/snippet}

<Row {id} {label} {description} control={control ?? (value !== undefined ? plain : undefined)} {below} />

<style>
  .lr-value {
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-fg);
  }
</style>
