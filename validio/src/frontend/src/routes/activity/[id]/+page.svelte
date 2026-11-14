<script lang="ts">
  /// Activity detail (builder A): asked, checked at Valio, the rule that
  /// decided, result, Proof folded; approve or reject in place while waiting.
  /// Data: api.activityItem(id); approve: owner.code then api.approve(orderId).
  import { page } from "$app/state";
  import { PageHead } from "$lib/v2";

  const id = $derived(page.params.id ?? "");
</script>

<PageHead title={id} back={{ href: "/activity", label: "Activity" }} />
