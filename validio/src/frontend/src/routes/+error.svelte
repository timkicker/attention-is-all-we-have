<script lang="ts">
  /// A page that is not here, or one that broke (plans/025, F1). The band and the dock stay, so the
  /// way back is where it always is; the page says what happened and offers the next step.
  import { page } from "$app/state";
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import { PageHead } from "$lib/v2";

  const missing = $derived(page.status === 404);
  const detail = $derived(page.error?.message && page.error.message !== "Not Found" ? page.error.message : "");
</script>

<div class="err" data-testid="error-page">
  {#if missing}
    <PageHead title="This page isn't here">
      <p class="lead">The address <span class="path" data-raw>{page.url.pathname}</span> doesn't open anything in Validio.</p>
    </PageHead>
    <div class="blocks">
      <div class="v-buttons">
        <Button href="/" id="error-home">Go to Home</Button>
        <Button href="/activity" variant="outline" id="error-activity">Open Activity</Button>
      </div>
    </div>
  {:else}
    <PageHead title="Something went wrong">
      <p class="lead">This page stopped while it was loading. Nothing you did was lost{#if detail}: <span class="path" data-raw>{detail}</span>{/if}.</p>
    </PageHead>
    <div class="blocks">
      <div class="v-buttons">
        <Button id="error-retry" onclick={() => location.reload()}>Try again</Button>
        <Button href="/" variant="outline" id="error-home">Go to Home</Button>
      </div>
    </div>
  {/if}
  <p class="code num" aria-hidden="true">{page.status}</p>
</div>

<style>
  .err {
    position: relative;
  }
  .path {
    font-family: var(--font-mono);
    font-size: 0.92em;
    overflow-wrap: anywhere;
  }
  .code {
    margin: 64px 0 0;
    font-family: var(--v-script);
    font-size: 72px;
    line-height: 1;
    color: var(--v-line-strong);
    user-select: none;
  }
</style>
