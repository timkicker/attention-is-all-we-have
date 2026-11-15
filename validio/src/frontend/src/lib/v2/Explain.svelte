<script lang="ts">
  /// An info button that opens a short explanation in place (plans/023). The popover grows out of
  /// the icon (app.css sets its transform-origin to bits-ui's computed one).
  import type { Snippet } from "svelte";
  import { Info } from "@lucide/svelte";
  import * as Popover from "@arlen/ui-kit/components/ui/popover";

  let { label, children }: { label: string; children: Snippet } = $props();
</script>

<Popover.Root>
  <Popover.Trigger class="xp" aria-label={label}>
    <Info size={14} strokeWidth={1.9} aria-hidden="true" />
  </Popover.Trigger>
  <Popover.Content class="xp-body" side="top" align="start">
    {@render children()}
  </Popover.Content>
</Popover.Root>
