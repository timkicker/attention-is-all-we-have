<script lang="ts">
  /// One timeline line, the same on Home and Activity: time, the outcome as a
  /// coloured word on a thin rule, title with the why under it, amount, and
  /// the whole row a link to its detail. Desk: one line in four columns.
  /// Phone: outcome and amount on top, then title, why and time. Put rows
  /// inside a ListSection (the ruled list).
  ///
  /// Motion (plans/002, 003, 018, 020): a press darkens the row at once; keyboard focus
  /// draws the ring inside the row with the hover look; the clicked row's title travels
  /// into the detail's heading; a pointer resting on the row fetches its detail ahead.
  import { onDestroy } from "svelte";
  import { api, LIVE } from "$lib/api/client";
  import type { ActivityItem } from "$lib/api/types";
  import { prime } from "$lib/live-cache";
  import { blurSwap } from "$lib/motion";
  import { net, tick } from "$lib/net.svelte";
  import { session } from "$lib/owner.svelte";
  import { morph, peek } from "$lib/peek.svelte";
  import { highlight, hm, nb, total } from "./format";
  import StatusPill from "./StatusPill.svelte";
  import { pillOf } from "./status";

  let {
    item,
    href = `/activity/${encodeURIComponent(item.id)}`,
    showTime = true,
    query = "",
  }: {
    item: ActivityItem;
    /** Defaults to the item's detail page. */
    href?: string;
    showTime?: boolean;
    /** Words to mark in the title and why (Activity's Find). */
    query?: string;
  } = $props();
  const tone = $derived(pillOf(item).tone);

  // The lists' rows, so a detail can show its title before its own answer.
  $effect.pre(() => {
    peek.set(item.id, item);
  });

  // Live only: the fixture runs on the frozen demo clock.
  const stop = LIVE ? tick(15_000) : null;
  onDestroy(() => stop?.());
  const when = $derived.by(() => {
    if (!LIVE) return hm(item.at);
    const ago = net.now - new Date(item.at).getTime();
    if (ago < 60_000) return "Just now";
    if (ago < 3_600_000) return `${Math.floor(ago / 60_000)} min ago`;
    return hm(item.at);
  });

  function onclick(e: MouseEvent) {
    if (!e.metaKey && !e.ctrlKey && !e.shiftKey && !e.altKey && e.button === 0) morph.id = item.id;
  }

  // Fetch ahead when a pointer rests on the row, a finger lands on it, or it gets focus.
  let timer: ReturnType<typeof setTimeout> | undefined;
  function warm() {
    const who = session.account?.id ?? "-";
    prime(`${who}:item:${item.id}`, () => api.activityItem(item.id));
    if (item.kind === "request") prime(`${who}:request:${item.id}`, () => api.request(item.id));
  }
  const rest = () => {
    clearTimeout(timer);
    timer = setTimeout(warm, 80);
  };
  const leave = () => clearTimeout(timer);
  onDestroy(leave);

  const titleParts = $derived(highlight(nb(item.title), query));
  const whyParts = $derived(highlight(nb(item.why), query));
</script>

{#snippet marked(parts: { text: string; hit: boolean }[])}{#each parts as p, i (i)}{#if p.hit}<mark>{p.text}</mark>{:else}{p.text}{/if}{/each}{/snippet}

<a
  class="ar"
  class:no-time={!showTime}
  {href}
  id="activity-{item.id}"
  data-testid="activity-{item.id}"
  data-status={item.status}
  {onclick}
  onpointerenter={rest}
  onpointerleave={leave}
  ontouchstart={warm}
  onfocus={warm}
>
  {#if showTime}<span class="ar-time num">{#key when}<span in:blurSwap>{when}</span>{/key}</span>{/if}
  <span class="ar-pill tone-{tone}"><StatusPill item={item} /></span>
  <span class="ar-main">
    <span class="ar-title" style:view-transition-name={morph.id === item.id ? "v-title" : undefined}>{@render marked(titleParts)}</span>
    <span class="ar-why">{@render marked(whyParts)}</span>
  </span>
  <span class="ar-end num">{nb(total(item.totalCents))}</span>
</a>

<style>
  .ar {
    display: grid;
    grid-template-columns: 72px 152px minmax(0, 1fr) auto;
    column-gap: 24px;
    align-items: baseline;
    align-content: center;
    min-height: 64px;
    padding: 14px 10px;
    color: inherit;
    text-decoration: none;
    transition: background-color var(--duration-fast) ease;
  }
  .ar.no-time {
    grid-template-columns: 152px minmax(0, 1fr) auto;
  }
  @media (hover: hover) and (pointer: fine) {
    .ar:hover {
      background: var(--v-tint-hover);
    }
    .ar:hover .ar-title {
      color: var(--valio);
    }
  }
  .ar:active {
    background: var(--v-tint-fill);
    transition-duration: 0ms;
  }
  /* On the darker press wash the faint time drops under 4.5:1; it takes the muted colour. */
  .ar:active .ar-time {
    color: var(--v-muted);
  }
  .ar:focus-visible {
    outline-offset: -2px;
    background: var(--v-tint-hover);
  }
  .ar:focus-visible .ar-title {
    color: var(--valio);
  }
  .ar-time {
    display: inline-grid;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-faint);
    white-space: nowrap;
  }
  .ar-time > span {
    grid-area: 1 / 1;
  }
  /* The outcome: its word in its colour, a thin rule of the same colour before it. */
  .ar-pill {
    display: flex;
    padding-left: 10px;
    border-left: 2px solid var(--v-line-strong);
  }
  .ar-pill.tone-ok {
    border-left-color: var(--v-ok);
  }
  .ar-pill.tone-bad {
    border-left-color: var(--v-bad);
  }
  .ar-pill.tone-wait {
    border-left-color: var(--valio);
  }
  .ar-main {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }
  .ar-title {
    font-size: var(--fs-body);
    line-height: var(--lh-body);
    font-weight: 500;
    overflow-wrap: anywhere;
    transition: color var(--duration-fast) ease;
  }
  .ar-why {
    margin-top: 2px;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-muted);
  }
  mark {
    padding: 0 2px;
    border-radius: var(--radius-chip);
    background: var(--valio-tint);
    color: inherit;
  }
  .ar-end {
    font-size: var(--fs-body);
    line-height: var(--lh-body);
    white-space: nowrap;
    text-align: right;
  }
  @media (max-width: 760px) {
    .ar,
    .ar.no-time {
      grid-template-columns: minmax(0, 1fr) auto;
      row-gap: 4px;
      padding: 14px 0;
    }
    .ar:focus-visible {
      padding-inline: 8px;
    }
    .ar-pill {
      grid-row: 1;
      grid-column: 1;
    }
    .ar-end {
      grid-row: 1;
      grid-column: 2;
    }
    .ar-main {
      grid-column: 1 / -1;
    }
    .ar-time {
      grid-row: 3;
      grid-column: 1 / -1;
    }
  }
</style>
