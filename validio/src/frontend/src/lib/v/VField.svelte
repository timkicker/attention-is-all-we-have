<script lang="ts">
  /// One labelled field: the label above, the kit Input, and the problem
  /// under it when there is one. Login, sign up and Settings use it.
  import type { HTMLInputAttributes } from "svelte/elements";
  import { Input } from "@arlen/ui-kit/components/ui/input";
  import { blurSwap } from "$lib/motion";

  let {
    id,
    label,
    value = $bindable(""),
    problem = "",
    hint = "",
    ...rest
  }: HTMLInputAttributes & { id: string; label: string; value?: string; problem?: string; hint?: string } = $props();
</script>

<div class="vf" class:bad={!!problem}>
  <label for={id}>{label}</label>
  <Input
    {id}
    data-testid={id}
    bind:value
    aria-invalid={problem ? true : undefined}
    aria-describedby={problem || hint ? `${id}-help` : undefined}
    {...rest}
  />
  <!-- The problem replaces the hint in place, through a soft blur (plans/019). -->
  {#if problem}
    {#key problem}<p class="help" id="{id}-help" data-testid="{id}-problem" role="alert" in:blurSwap={{ y: 3 }}>{problem}</p>{/key}
  {:else if hint}
    <p class="help" id="{id}-help" in:blurSwap={{ y: 3 }}>{hint}</p>
  {/if}
</div>

<style>
  .vf {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  label {
    font-size: var(--fs-head);
    line-height: var(--lh-meta);
    font-weight: 500;
    transition: color var(--duration-fast) ease;
  }
  .vf:focus-within label {
    color: var(--valio);
  }
  .bad:focus-within label {
    color: var(--v-bad-text);
  }
  .help {
    margin: 0;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-muted);
  }
  .bad .help {
    color: var(--v-bad-text);
  }
</style>
