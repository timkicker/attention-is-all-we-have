<script lang="ts">
  /// Settings: one page. On the desk the section list stands on the left and
  /// jumps to its section; on the phone the sections follow one another in
  /// one list, Log out last.
  import { onMount } from "svelte";
  import { chrome } from "$lib/chrome.svelte";
  import { session } from "$lib/owner.svelte";
  import { settingsApi, type Settings } from "$lib/settings";
  import VHead from "$lib/v/VHead.svelte";
  import VState from "$lib/v/VState.svelte";
  import Diet from "./Diet.svelte";
  import Kitchen from "./Kitchen.svelte";
  import Login from "./Login.svelte";
  import Theme from "./Theme.svelte";
  import { logOut, SECTIONS, type SectionId } from "./sections";

  let s = $state<Settings | undefined>();
  let error = $state("");
  const load = () =>
    settingsApi.get().then(
      (v) => ((s = v), (error = "")),
      (e) => (error = e instanceof Error ? e.message : String(e)),
    );
  onMount(load);
  const saved = (v: Settings) => (s = v);

  let here = $state<SectionId>("kitchen");
  onMount(() => {
    const h = location.hash.slice(1);
    if (SECTIONS.some((x) => x.id === h)) here = h as SectionId;
  });
</script>

<VHead title="Settings" />

<div class="set" class:phone={chrome.phone}>
  {#if !chrome.phone}
    <nav class="set-nav" aria-label="Settings">
      {#each SECTIONS as x (x.id)}
        <a
          href="#{x.id}"
          id="set-nav-{x.id}"
          data-testid="set-nav-{x.id}"
          class="set-item"
          class:on={here === x.id}
          aria-current={here === x.id ? "location" : undefined}
          onclick={() => (here = x.id)}>{x.label}</a
        >
      {/each}
      <button type="button" class="set-item out" data-testid="log-out" onclick={logOut}>Log out</button>
    </nav>
  {/if}
  <div class="set-body">
    {#if !s}
      {#if error}
        <VState kind="error" title="Validio is not reachable." detail={error} onretry={load} />
      {:else}
        <VState kind="loading" rows={3} />
      {/if}
    {:else}
      {#each SECTIONS as x (x.id)}
        <section class="sec" id={x.id} aria-labelledby="h-{x.id}" data-testid="settings-{x.id}">
          <h2 class="v-h" id="h-{x.id}">{x.label}</h2>
          {#if x.id === "kitchen"}
            <Kitchen {s} onsaved={saved} />
          {:else if x.id === "diet"}
            <Diet {s} onsaved={saved} />
          {:else if x.id === "login"}
            <Login {s} demo={!!session.account?.isDemo} onsaved={saved} />
          {:else}
            <Theme />
          {/if}
        </section>
      {/each}
      {#if chrome.phone}
        <button type="button" class="out-row" data-testid="log-out" onclick={logOut}>Log out</button>
      {/if}
    {/if}
  </div>
</div>

<style>
  .set {
    margin-top: 32px;
    display: grid;
    grid-template-columns: 200px minmax(0, 1fr);
    gap: 32px;
    align-items: start;
  }
  .set.phone {
    grid-template-columns: minmax(0, 1fr);
  }
  .set-nav {
    display: flex;
    flex-direction: column;
    gap: 2px;
    position: sticky;
    top: 48px;
  }
  .set-item {
    display: flex;
    align-items: center;
    height: 32px;
    padding: 0 8px;
    margin: 0;
    border: 0;
    border-radius: var(--radius-button);
    background: none;
    font: inherit;
    font-size: var(--fs-meta);
    line-height: 20px;
    color: var(--v-muted);
    text-align: left;
    text-decoration: none;
    white-space: nowrap;
    cursor: pointer;
  }
  .set-item:hover:not(.on) {
    background: var(--v-tint-hover);
    color: var(--v-fg);
  }
  .set-item.on {
    color: var(--v-fg);
    font-weight: 500;
    background: var(--v-tint-hover);
  }
  .set-item.out {
    margin-top: 12px;
  }
  .set-body {
    min-width: 0;
  }
  .sec {
    scroll-margin-top: 48px;
  }
  .sec + .sec {
    margin-top: 32px;
  }
  .out-row {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    min-height: 44px;
    margin: 32px 0 0;
    border: 1px solid var(--border);
    border-radius: var(--radius-button);
    background: none;
    font: inherit;
    font-size: var(--fs-body);
    color: var(--v-bad-text);
    cursor: pointer;
  }
  .out-row:hover {
    background: var(--v-tint-hover);
  }
</style>
