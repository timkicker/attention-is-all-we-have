<script lang="ts">
  /// Settings: one page. On the desk the sections stand in a list on the left
  /// and the chosen one on the right; on the phone /settings is that list and
  /// each section is its own page with the way back.
  import { page } from "$app/state";
  import { chrome } from "$lib/chrome.svelte";
  import { SECTIONS, logOut } from "./sections";
  import VHead from "$lib/v/VHead.svelte";

  let { children } = $props();
  const here = $derived(page.url.pathname.split("/")[2] ?? "");
</script>

{#if chrome.phone}
  {@render children()}
{:else}
  <VHead title="Settings" />
  <div class="set">
    <nav class="set-nav" aria-label="Settings">
      {#each SECTIONS as s (s.id)}
        <a
          href="/settings/{s.id}"
          id="set-nav-{s.id}"
          data-testid="set-nav-{s.id}"
          class="set-item"
          class:on={here === s.id}
          aria-current={here === s.id ? "page" : undefined}>{s.label}</a
        >
      {/each}
      <button type="button" class="set-item out" data-testid="log-out" onclick={logOut}>Log out</button>
    </nav>
    <div class="set-pane">{@render children()}</div>
  </div>
{/if}

<style>
  .set {
    margin-top: 32px;
    display: grid;
    grid-template-columns: 200px minmax(0, 1fr);
    gap: 32px;
    align-items: start;
  }
  .set-nav {
    display: flex;
    flex-direction: column;
    gap: 2px;
    position: sticky;
    top: 16px;
  }
  .set-item {
    position: relative;
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
  .set-pane {
    min-width: 0;
  }
</style>
