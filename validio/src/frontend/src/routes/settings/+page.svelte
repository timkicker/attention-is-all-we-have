<script lang="ts">
  /// Settings: Kitchen, Login, Approval code, Theme, then Log out. One
  /// column of rows; each change opens under its own row. The diet moved to
  /// the Rules.
  import { onMount } from "svelte";
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import { session } from "$lib/owner.svelte";
  import { settingsApi, type Settings } from "$lib/settings";
  import { Loading, LoadError, PageHead } from "$lib/v2";
  import Code from "./Code.svelte";
  import Kitchen from "./Kitchen.svelte";
  import Login from "./Login.svelte";
  import Theme from "./Theme.svelte";
  import { logOut } from "./sections";

  let s = $state<Settings | undefined>();
  let error = $state("");
  const load = () =>
    settingsApi.get().then(
      (v) => ((s = v), (error = "")),
      (e) => (error = e instanceof Error ? e.message : String(e)),
    );
  onMount(load);
  const saved = (v: Settings) => (s = v);
  const demo = $derived(!!session.account?.isDemo);
</script>

<PageHead title="Settings" />

<div class="blocks" class:v-arrive={!!s}>
  {#if !s}
    {#if error}
      <LoadError detail={error} onretry={load} />
    {:else}
      <Loading rows={4} />
    {/if}
  {:else}
    <Kitchen {s} onsaved={saved} />
    <Login {s} {demo} onsaved={saved} />
    <Code {demo} />
    <Theme />
    <div class="out">
      <Button variant="outline" id="log-out" data-testid="log-out" onclick={logOut}>Log out</Button>
    </div>
  {/if}
</div>

<style>
  .blocks {
    display: flex;
    flex-direction: column;
    gap: 32px;
  }
  .blocks > :global(*) {
    margin: 0;
  }
</style>
