<script lang="ts">
  /// Skeleton rows in the final geometry (kit Skeleton), then "Still loading". Wraps VState.
  import VState from "$lib/v/VState.svelte";
  let { rows = 3 }: { rows?: number } = $props();
</script>

<VState kind="loading" {rows} />
