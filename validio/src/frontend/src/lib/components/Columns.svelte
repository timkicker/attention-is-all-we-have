<script lang="ts">
  // A page with a main column and a narrower side column on wide screens.
  // Below 1100px the side column follows the main one.
  import type { Snippet } from "svelte";

  let { main, aside }: { main: Snippet; aside?: Snippet } = $props();
</script>

<div class="cols" class:single={!aside}>
  <div class="main">{@render main()}</div>
  {#if aside}<aside class="aside">{@render aside()}</aside>{/if}
</div>

<style>
  .cols {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 20rem;
    gap: var(--space-section, 1.5rem);
    width: 100%;
    max-width: var(--width-section-body);
    margin-inline: auto;
    align-items: start;
  }
  .cols.single {
    grid-template-columns: minmax(0, 1fr);
  }
  .main,
  .aside {
    display: flex;
    flex-direction: column;
    gap: var(--space-section, 1.5rem);
    min-width: 0;
  }
  @media (max-width: 1100px) {
    .cols {
      grid-template-columns: minmax(0, 1fr);
    }
  }
</style>
