<script lang="ts">
  /// An explanation behind an (i), never as a standing paragraph.
  import * as Popover from "@arlen/ui-kit/components/ui/popover";
  import { Info } from "@lucide/svelte";

  let { label, text, id }: { label: string; text: string; id?: string } = $props();
</script>

<Popover.Root>
  <Popover.Trigger>
    {#snippet child({ props })}
      <button {...props} type="button" class="info" aria-label={label} {id}>
        <Info size={15} strokeWidth={1.75} />
      </button>
    {/snippet}
  </Popover.Trigger>
  <Popover.Content class="w-72 text-sm" align="start">{text}</Popover.Content>
</Popover.Root>

<style>
  .info {
    display: inline-grid;
    place-items: center;
    width: 1.5rem;
    height: 1.5rem;
    border-radius: var(--radius-button);
    color: var(--color-fg-secondary);
    vertical-align: middle;
    transition: background-color var(--duration-fast) var(--ease-default);
  }
  .info:hover {
    background: color-mix(in srgb, var(--color-fg-primary) 8%, transparent);
    color: var(--color-fg-primary);
  }
</style>
