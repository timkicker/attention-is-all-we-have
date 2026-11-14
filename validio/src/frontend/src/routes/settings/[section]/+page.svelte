<script lang="ts">
  /// One Settings section. On the phone it is a page of its own with the way
  /// back to the list; on the desk it stands beside the list (+layout).
  import { onMount } from "svelte";
  import { page } from "$app/state";
  import { chrome } from "$lib/chrome.svelte";
  import { session } from "$lib/owner.svelte";
  import { settingsApi, type Settings } from "$lib/settings";
  import VHead from "$lib/v/VHead.svelte";
  import VState from "$lib/v/VState.svelte";
  import { SECTIONS } from "../sections";
  import Diet from "../Diet.svelte";
  import Kitchen from "../Kitchen.svelte";
  import Login from "../Login.svelte";
  import Theme from "../Theme.svelte";

  const sec = $derived(SECTIONS.find((x) => x.id === page.params.section));
  let s = $state<Settings | undefined>();
  let error = $state("");
  const load = () =>
    settingsApi.get().then(
      (v) => ((s = v), (error = "")),
      (e) => (error = e instanceof Error ? e.message : String(e)),
    );
  onMount(load);
  const saved = (v: Settings) => (s = v);
</script>

{#if chrome.phone}
  <VHead title={sec?.label ?? "Settings"} back={{ href: "/settings", label: "Settings" }} />
{/if}

<section class="pane" aria-label={sec?.label} data-testid="settings-{sec?.id ?? 'none'}">
  {#if !sec}
    <VState kind="empty" title="No such section." />
  {:else if sec.id === "theme"}
    <Theme />
  {:else if !s}
    {#if error}
      <VState kind="error" title="Validio is not reachable." detail={error} onretry={load} />
    {:else}
      <VState kind="loading" rows={3} />
    {/if}
  {:else if sec.id === "kitchen"}
    <Kitchen {s} onsaved={saved} />
  {:else if sec.id === "diet"}
    <Diet {s} onsaved={saved} />
  {:else if sec.id === "login"}
    <Login {s} demo={!!session.account?.isDemo} onsaved={saved} />
  {/if}
</section>

<style>
  .pane {
    min-width: 0;
  }
</style>
