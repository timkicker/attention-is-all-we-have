<script lang="ts">
  /// A state word: the kit Badge as it is, one shape for every state. Colour
  /// and word carry it, no dot (the kit's rule). A list lines its badges up in
  /// its own column, the badge keeps its own width.
  import { Badge } from "@arlen/ui-kit/components/ui/badge";
  import type { Tone } from "$lib/format";

  let { label, tone, id }: { label: string; tone: Tone; id?: string } = $props();

  const variant = $derived(
    tone === "ok" ? "success" : tone === "bad" ? "destructive" : tone === "act" ? "secondary" : "outline",
  );
</script>

<Badge {variant} {id}>{label}</Badge>
