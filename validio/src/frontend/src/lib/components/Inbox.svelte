<script lang="ts">
  /// The inbox as Arlen mail lays it out: the list in a 21rem column, the open
  /// request beside it. On the phone one of the two at a time.
  import { api } from "$lib/api/client";
  import { live } from "$lib/live.svelte";
  import InboxList from "./InboxList.svelte";
  import RequestPane from "./RequestPane.svelte";

  let { selected }: { selected?: string } = $props();

  const inbox = live(() => api.inbox());
  const req = live(() => (selected ? api.request(selected) : Promise.resolve(undefined)));
  const pass = live(() => api.spendPass("M-1"));
  let paneEl = $state<HTMLElement | undefined>();
  // A newly opened request starts at its top, as a mail does.
  $effect(() => {
    void selected;
    if (paneEl) paneEl.scrollTop = 0;
  });
  const waiting = $derived((inbox.data ?? []).filter((i) => i.status === "waiting").length);
</script>

<div class="split" class:has={!!selected}>
  <div class="col">
    <div class="col-head">
      <span class="count num">{inbox.data?.length ?? 0} {inbox.data?.length === 1 ? "request" : "requests"}</span>
      {#if waiting}<span class="count num">{waiting} waiting for you</span>{/if}
    </div>
    {#if inbox.error && !inbox.data}
      <p class="msg">Cannot reach Validio: {inbox.error}</p>
    {:else if inbox.data}
      <InboxList items={inbox.data} {selected} />
    {/if}
  </div>
  <div class="pane" bind:this={paneEl}>
    {#if !selected}
      <div class="none">
        <p>Pick a request to see what Validio did and why.</p>
      </div>
    {:else if req.data && req.data.id === selected}
      <RequestPane req={req.data} pass={pass.data} />
    {:else if req.error}
      <p class="msg">Request {selected}: {req.error}</p>
    {/if}
  </div>
</div>

<style>
  .split {
    display: flex;
    height: 100%;
    min-height: 0;
  }
  .col {
    display: flex;
    flex: 0 1 21rem;
    flex-direction: column;
    min-width: 13rem;
    border-inline-end: 1px solid var(--color-border);
    overflow-y: auto;
  }
  .col-head {
    display: flex;
    justify-content: space-between;
    gap: 0.5rem;
    padding: 0.75rem 1.05rem 0.25rem;
  }
  .count {
    font-size: var(--text-2xs);
    color: var(--color-fg-secondary);
  }
  .pane {
    flex: 1;
    min-width: 0;
    overflow-y: auto;
  }
  .none {
    display: grid;
    place-items: center;
    height: 100%;
    padding: 2rem;
    font-size: var(--text-sm);
    color: var(--color-fg-secondary);
  }
  .msg {
    padding: 1rem 1.25rem;
    font-size: var(--text-sm);
    color: var(--color-fg-secondary);
  }
  @media (max-width: 760px) {
    .split {
      height: auto;
    }
    .col {
      flex: 1;
      border: 0;
      overflow: visible;
    }
    .pane {
      display: none;
      overflow: visible;
    }
    .has .col {
      display: none;
    }
    .has .pane {
      display: block;
    }
  }
</style>
