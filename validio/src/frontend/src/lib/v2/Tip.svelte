<script lang="ts">
  /// A tooltip on hover and keyboard focus (plans/023). The layout's Tooltip.Provider sets the
  /// timing: the first waits 500 ms, any other within 300 ms of one closing opens at once and
  /// without animation (app.css, data-state="instant-open").
  import type { Snippet } from "svelte";
  import { Tooltip } from "bits-ui";
  import { TooltipContent } from "@arlen/ui-kit/components/ui/tooltip";

  let { text, disabled = false, children }: { text: string; disabled?: boolean; children: Snippet<[Record<string, unknown>]> } = $props();
</script>

{#if disabled}
  {@render children({})}
{:else}
  <Tooltip.Root>
    <Tooltip.Trigger>
      {#snippet child({ props })}{@render children(props)}{/snippet}
    </Tooltip.Trigger>
    <TooltipContent>{text}</TooltipContent>
  </Tooltip.Root>
{/if}
