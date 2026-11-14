<script lang="ts">
  /// The page's data did not come: what went wrong and Retry. Wraps VState.
  import VState from "$lib/v/VState.svelte";
  let { detail = "", onretry }: { detail?: string; onretry?: () => void } = $props();
</script>

<VState kind="error" title="Validio is not reachable" {detail} onretry={onretry ?? (() => location.reload())} />
