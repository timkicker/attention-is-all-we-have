<script lang="ts">
  /// halbat's states: empty, loading (skeletons in the final geometry, then
  /// "Still loading"), and a load failure with Retry. Neutral, never blue or red.
  import { onDestroy } from "svelte";
  import { Skeleton } from "@arlen/ui-kit/components/ui/skeleton";
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import { CircleAlert, Inbox, LoaderCircle } from "@lucide/svelte";
  import { rise } from "$lib/motion";

  let {
    kind,
    title = "",
    detail = "",
    onretry,
    rows = 2,
  }: { kind: "empty" | "loading" | "error"; title?: string; detail?: string; onretry?: () => void; rows?: number } = $props();

  let secs = $state(0);
  const t = setInterval(() => (secs += 1), 1000);
  onDestroy(() => clearInterval(t));
</script>

{#if kind === "loading"}
  <div class="sk" aria-busy="true" aria-label="Loading">
    <Skeleton class="sk-h1" />
    <Skeleton class="sk-facts" />
    {#each Array(rows) as _, i (i)}<Skeleton class="sk-row" />{/each}
    {#if secs >= 10}
      <p class="vs" class:long={secs >= 30} role="status" in:rise={{ y: 4, duration: 200 }}>
        <LoaderCircle size={16} strokeWidth={1.75} aria-hidden="true" />
        <span>{secs >= 30 ? "Taking longer than usual" : "Still loading"} {secs} s</span>
      </p>
    {/if}
  </div>
{:else}
  <div class="vs-block" role={kind === "error" ? "alert" : undefined}>
    <p class="vs-title">
      {#if kind === "error"}<CircleAlert size={16} strokeWidth={1.75} aria-hidden="true" class="crit" />{:else}<Inbox size={16} strokeWidth={1.75} aria-hidden="true" class="faint" />{/if}
      {title}
    </p>
    {#if detail}<p class="vs-detail">{detail}</p>{/if}
    {#if onretry}<Button variant="outline" onclick={onretry}>Retry</Button>{/if}
  </div>
{/if}

<style>
  /* The skeleton waits 150 ms before it fades in: a fast answer never shows it (plans/004). */
  .sk {
    animation: v-sk-in var(--v-dur-ui) var(--v-ease-out) 150ms both;
  }
  @keyframes v-sk-in {
    from {
      opacity: 0;
    }
  }
  .sk {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .sk :global(.sk-h1) {
    width: 320px;
    max-width: 100%;
    height: 24px;
  }
  .sk :global(.sk-facts) {
    width: 400px;
    max-width: 100%;
    height: 14px;
    margin-bottom: 20px;
  }
  .sk :global(.sk-row) {
    height: 56px;
  }
  .vs {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 0;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-muted);
  }
  .vs.long {
    color: var(--v-fg);
  }
  .vs-block {
    padding: 24px 0;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
  }
  .vs-title {
    margin: 0;
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: var(--fs-body);
    line-height: var(--lh-body);
    font-weight: 500;
  }
  .vs-detail {
    margin: 0 0 8px;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-muted);
  }
  .vs-title :global(.faint) {
    color: var(--v-faint);
  }
  .vs-title :global(.crit) {
    color: var(--v-bad-text);
  }
</style>
