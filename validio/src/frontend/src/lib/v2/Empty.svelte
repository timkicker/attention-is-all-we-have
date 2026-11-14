<script lang="ts">
  /// Nothing here yet: one line, an optional second one. Wraps VState.
  import VState from "$lib/v/VState.svelte";
  let { title, detail = "" }: { title: string; detail?: string } = $props();
</script>

<VState kind="empty" {title} {detail} />
