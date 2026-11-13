<script lang="ts">
  import { Badge } from "@arlen/ui-kit/components/ui/badge";
  import type { RequestStatus } from "$lib/api/types";
  import { STATUS } from "$lib/format";

  let { status }: { status: RequestStatus } = $props();
  const s = $derived(STATUS[status]);
</script>

<Badge variant={s.variant} data-status={status}>{s.label}</Badge>
