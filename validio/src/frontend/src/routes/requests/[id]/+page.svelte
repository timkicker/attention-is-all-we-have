<script lang="ts">
  import { page } from "$app/state";
  import Inbox from "$lib/components/Inbox.svelte";
  import { setChrome } from "$lib/chrome.svelte";

  const id = $derived(page.params.id ?? "");
  $effect(() => setChrome(`Request ${id}`, { href: "/", label: "Inbox" }));
</script>

<Inbox selected={id} />
