<script lang="ts">
  /// A number field for a Rules row: the kit Input, its unit beside it (€ or
  /// %), and the problem under it. The row's label names the field.
  import { collapse } from "$lib/motion";
  import { Input } from "@arlen/ui-kit/components/ui/input";

  let {
    id,
    label,
    unit,
    value = $bindable(""),
    problem = "",
    placeholder = "",
    narrow = false,
    start = false,
    onblur,
  }: {
    id: string;
    /** The accessible name: the row label above says it to the eye. */
    label: string;
    unit: string;
    value?: string;
    problem?: string;
    placeholder?: string;
    /** A percentage: a short field. */
    narrow?: boolean;
    /** Under its label (the phone): field and problem start on the left. */
    start?: boolean;
    onblur?: () => void;
  } = $props();
</script>

<div class="uf" class:narrow class:start>
  <div class="uf-line">
    <Input
      {id}
      data-testid={id}
      bind:value
      inputmode="decimal"
      autocomplete="off"
      aria-label={label}
      aria-invalid={problem ? true : undefined}
      aria-describedby={problem ? `${id}-problem` : undefined}
      {placeholder}
      {onblur}
      class="uf-input num"
    />
    <span class="uf-unit" aria-hidden="true">{unit}</span>
  </div>
  {#if problem}<p class="uf-problem" id="{id}-problem" data-testid="{id}-problem" in:collapse={{ duration: 200 }} out:collapse={{ duration: 140 }}>{problem}</p>{/if}
</div>

<style>
  .uf {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 4px;
  }
  .uf.start {
    align-items: flex-start;
  }
  .start .uf-problem {
    padding-right: 0;
    text-align: left;
  }
  .uf-line {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .uf-line :global(.uf-input) {
    width: 144px;
    text-align: right;
  }
  .narrow .uf-line :global(.uf-input) {
    width: 64px;
  }
  .uf-unit {
    width: 16px;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-muted);
  }
  .uf-problem {
    max-width: 320px;
    margin: 0;
    padding-right: 24px;
    text-align: right;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-bad-text);
  }
</style>
