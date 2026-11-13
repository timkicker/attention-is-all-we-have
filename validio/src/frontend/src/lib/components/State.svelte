<script lang="ts">
  /// A state word on the kit Badge, one width per column so a list of them
  /// lines up. Success and error carry the kit's tint; a call to act is the
  /// neutral secondary fill with an icon; everything else is outline.
  import { Badge } from "@arlen/ui-kit/components/ui/badge";
  import { Hand } from "@lucide/svelte";
  import type { Tone } from "$lib/format";

  let { label, tone, id }: { label: string; tone: Tone; id?: string } = $props();

  const variant = $derived(
    tone === "ok" ? "success" : tone === "bad" ? "destructive" : tone === "act" ? "secondary" : "outline",
  );
</script>

<Badge {variant} {id} class="state {tone}">
  {#if tone === "act"}<Hand data-icon="inline-start" strokeWidth={2} />{/if}
  {label}
</Badge>

<style>
  :global(.state) {
    min-width: 6.6em;
  }
  :global(.state.act) {
    border-color: var(--color-border);
    color: var(--color-fg-primary);
  }
</style>
