<script lang="ts">
  /// Every tag in the app: a state word, or with `count` the waiting number in
  /// the sidebar and dock. The kit Badge at the kit's chip radius, in one of the
  /// four tones. No dot.
  import { Badge } from "@arlen/ui-kit/components/ui/badge";
  import type { PillTone } from "$lib/v";

  let {
    label,
    tone,
    count = false,
    testid,
    id,
  }: { label: string; tone: PillTone; count?: boolean; testid?: string; id?: string } = $props();
</script>

<Badge variant="outline" class="v-pill tone-{tone}{count ? ' v-count' : ''}" data-testid={testid} {id} aria-hidden={count ? "true" : undefined}>{label}</Badge>
