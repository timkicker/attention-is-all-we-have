<script lang="ts">
  /// The status of a request or standing order: Ordered automatically, Approved by you,
  /// Waiting for you, Blocked or Standing. The app's VPill (kit Badge) in the status's tone.
  import type { ActivityItem } from "$lib/api/types";
  import VPill from "$lib/v/VPill.svelte";
  import { pillOf } from "./status";

  let { item, testid, id }: { item: Pick<ActivityItem, "status" | "approvedByYou">; testid?: string; id?: string } = $props();
  const pill = $derived(pillOf(item));
</script>

<VPill label={pill.label} tone={pill.tone} {testid} {id} />
