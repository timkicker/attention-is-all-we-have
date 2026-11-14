<script lang="ts">
  /// A state word: the kit Badge, outline variant, in a halbat tone. No dot.
  import { Badge } from "@arlen/ui-kit/components/ui/badge";
  import type { PillTone } from "$lib/v";

  let { label, tone, testid, id }: { label: string; tone: PillTone; testid?: string; id?: string } = $props();
</script>

<Badge variant="outline" class="v-pill tone-{tone}" data-testid={testid} {id}>{label}</Badge>
