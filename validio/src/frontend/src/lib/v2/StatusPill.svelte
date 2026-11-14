<script lang="ts">
  /// The status of a request or standing order: Ordered alone, Waiting for you,
  /// Blocked or Standing. The app's VPill (kit Badge) in the status's tone.
  import type { ActivityStatus } from "$lib/api/types";
  import VPill from "$lib/v/VPill.svelte";
  import { STATUS_PILL } from "./status";

  let { status, testid, id }: { status: ActivityStatus; testid?: string; id?: string } = $props();
  const pill = $derived(STATUS_PILL[status]);
</script>

<VPill label={pill.label} tone={pill.tone} {testid} {id} />
