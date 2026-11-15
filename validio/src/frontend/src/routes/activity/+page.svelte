<script lang="ts">
  /// Activity: everything the agent did, newest first under day heads. The
  /// filters are words with their counts, the chosen one underlined in petrol;
  /// they live in the address (?status=), so a filtered list can be linked and
  /// Back walks the filters. Find (?q=) narrows what is loaded and marks the words.
  ///
  /// Motion (plans/004, 005, 015, 022): a filter switch keeps the old list, dimmed, until the
  /// new one answers; the petrol bar slides to the chosen word; rows the agent adds slide in;
  /// day heads stay under the band while their day scrolls. Typing in Find moves nothing.
  import { goto } from "$app/navigation";
  import { page } from "$app/state";
  import { api } from "$lib/api/client";
  import type { ActivityFilter, ActivityItem } from "$lib/api/types";
  import { fold } from "$lib/v2/format";
  import { easeOut, reduced } from "$lib/motion";
  import { ActivityRow, byDay, Empty, FILTERS, isFilter, ListSection, live, LiveRows, Loading, LoadError, PageHead } from "$lib/v2";

  const status = $derived.by((): ActivityFilter => {
    const s = page.url.searchParams.get("status");
    return isFilter(s) ? s : "all";
  });
  const query = $derived(page.url.searchParams.get("q") ?? "");
  // Each answer names the filter it was asked for, so a switch never shows the old filter's rows.
  const list = live(
    async () => {
      const s = status;
      return { status: s, ...(await api.activity(s)) };
    },
    2000,
    () => `activity:${status}`,
  );
  const fresh = $derived(list.data?.status === status);

  const EMPTY: Record<ActivityFilter, string> = {
    all: "Nothing yet",
    ordered: "Nothing ordered yet",
    waiting: "Nothing waits for you",
    blocked: "Nothing blocked",
    standing: "No standing orders",
  };

  const shown = $derived.by((): ActivityItem[] => {
    const items = list.data?.items ?? [];
    const q = fold(query.trim());
    if (!q) return items;
    return items.filter((i) => fold(`${i.title} ${i.why}`).includes(q));
  });

  function url(f: ActivityFilter, q: string) {
    const p = new URLSearchParams();
    if (f !== "all") p.set("status", f);
    if (q) p.set("q", q);
    const s = p.toString();
    return s ? `/activity?${s}` : "/activity";
  }
  function pick(f: ActivityFilter) {
    if (f === status) return;
    void goto(url(f, query), { noScroll: true, keepFocus: true });
  }
  function find(q: string) {
    void goto(url(status, q), { noScroll: true, keepFocus: true, replaceState: true });
  }

  // The petrol bar under the chosen filter, moved with a transform (plans/015).
  let bar = $state<HTMLElement>();
  let ink = $state({ x: 0, w: 0 });
  let inkReady = $state(false);
  $effect(() => {
    void status;
    void list.data?.counts;
    const b = bar?.querySelector<HTMLElement>('button[aria-pressed="true"]');
    if (!b) return;
    ink = { x: b.offsetLeft, w: b.offsetWidth };
    if (!inkReady) requestAnimationFrame(() => requestAnimationFrame(() => (inkReady = true)));
  });

  // A new filter's list comes in slowly: it sharpens out of a 3 px blur while it rises 12 px.
  // Typing in Find changes the list too, but never animates (a keyboard action).
  const listIn = (_n: Element) =>
    reduced()
      ? { duration: 160, css: (t: number) => `opacity:${t}` }
      : { duration: 520, easing: easeOut, css: (t: number, u: number) => `opacity:${t};transform:translateY(${u * 12}px);filter:blur(${u * 3}px)` };

  // A day head is "stuck" under the band: it gains its hairline (plans/022).
  function stick(node: HTMLElement) {
    const head = node.nextElementSibling as HTMLElement | null;
    const top = matchMedia("(max-width: 760px)").matches ? 52 : 60;
    const io = new IntersectionObserver(([e]) => head?.classList.toggle("stuck", !e.isIntersecting && e.boundingClientRect.top < top + 1), {
      rootMargin: `-${top + 1}px 0px 0px 0px`,
    });
    io.observe(node);
    return () => io.disconnect();
  }
</script>

<PageHead title="Activity">
  <p class="lead">Everything your agent did, and why.</p>
</PageHead>

<!-- A kitchen with nothing yet gets no filters: five zeros say nothing. -->
{#if !list.data || list.data.counts.all > 0}
  <div class="bar-row">
    <div class="filters" role="group" aria-label="Show" bind:this={bar}>
      {#each FILTERS as f (f.id)}
        <button type="button" id="filter-{f.id}" aria-pressed={status === f.id} onclick={() => pick(f.id)}>
          {f.label}{#if list.data}<em>{list.data.counts[f.id]}</em>{/if}
        </button>
      {/each}
      <span class="f-ink" class:ready={inkReady} style:transform="translateX({ink.x}px) scaleX({ink.w})" aria-hidden="true"></span>
    </div>
    <input
      class="find"
      type="search"
      placeholder="Find"
      aria-label="Find in activity"
      id="activity-find"
      data-testid="activity-find"
      data-slot="input"
      value={query}
      oninput={(e) => find(e.currentTarget.value)}
      onkeydown={(e) => {
        if (e.key === "Escape" && query) {
          e.preventDefault();
          find("");
        }
      }}
    />
  </div>
{/if}

<div class="days" class:stale={!fresh && !!list.data} class:v-arrive={list.arrive} aria-busy={!fresh}>
  {#if list.error && !list.data}
    <LoadError detail={list.error} />
  {:else if !list.data}
    <Loading />
  {:else if fresh && !list.data.items.length}
    <Empty title={EMPTY[status]} detail={status === "all" ? "What your agent orders shows up here." : ""} />
  {:else if query && !shown.length}
    <Empty title="Nothing matches" detail="Try another word" />
  {:else}
    <!-- A new filter is a new list: it comes in as one. A new word in Find is simply there. -->
    <!-- Keyed on the filter the shown rows belong to, so it plays when they arrive, not before. -->
    {#key list.data.status}
     <div in:listIn>
    {#key query}
      <div>
        {#each byDay(shown) as g (g.key)}
          <section class="dg" aria-labelledby="day-{g.key}">
            <span class="sentinel" {@attach stick} aria-hidden="true"></span>
            <h2 class="v-h" id="day-{g.key}">{g.head}</h2>
            <ListSection id="day-{g.key}-rows">
              <LiveRows items={g.items}>{#snippet row(i)}<ActivityRow item={i} {query} />{/snippet}</LiveRows>
            </ListSection>
          </section>
        {/each}
      </div>
    {/key}
     </div>
    {/key}
  {/if}
</div>

<style>
  .bar-row {
    display: flex;
    align-items: flex-end;
    gap: 24px;
    margin-top: 32px;
    border-bottom: 1px solid var(--v-line);
  }
  .filters {
    position: relative;
    flex: 1 1 auto;
    min-width: 0;
    border-bottom: 0;
  }
  .f-ink {
    position: absolute;
    left: 0;
    bottom: -1px;
    width: 1px;
    height: 2px;
    background: var(--valio);
    transform-origin: left center;
    pointer-events: none;
  }
  .f-ink.ready {
    transition: transform var(--v-dur-ui) var(--v-ease-in-out);
  }
  .find {
    flex: none;
    width: 200px;
    height: var(--height-control);
    margin-bottom: 8px;
    padding: 0 10px;
    border: 1px solid var(--v-line-strong);
    border-radius: var(--radius-input);
    background: var(--v-surface);
    color: var(--v-fg);
    font: inherit;
    font-size: var(--fs-meta);
  }
  .find::placeholder {
    color: var(--v-faint);
  }
  @media (max-width: 760px) {
    .bar-row {
      flex-direction: column;
      align-items: stretch;
      gap: 12px;
      margin: 20px 0 0;
      border-bottom: 0;
    }
    /* One row that scrolls sideways on its own, edge to edge. */
    .filters {
      margin: 0 -16px;
      padding: 0 16px;
      border-bottom: 1px solid var(--v-line);
    }
    .filters button {
      flex: none;
    }
    .find {
      width: 100%;
      margin: 0;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .f-ink.ready {
      transition: none;
    }
  }
  .days {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-top: 8px;
    transition: opacity var(--v-dur-ui) var(--v-ease-out);
  }
  .days.stale {
    opacity: 0.55;
  }
  .dg {
    display: flex;
    flex-direction: column;
  }
  .sentinel {
    display: block;
    height: 0;
  }
  /* The day heads: small and quiet over the ruled list, and they stay while their day scrolls. */
  .dg .v-h {
    position: sticky;
    top: 60px;
    z-index: 2;
    min-height: 0;
    margin: 0;
    padding: 24px 0 8px;
    background: var(--v-ground);
    border-bottom: 1px solid transparent;
    font-family: var(--v-sans);
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    font-weight: 600;
    color: var(--v-muted);
    transition: border-color var(--duration-fast) ease;
  }
  .dg .v-h:global(.stuck) {
    border-bottom-color: var(--v-line);
  }
  @media (max-width: 760px) {
    .dg .v-h {
      top: 52px;
    }
  }
  .dg :global(.section-card) {
    border-top-color: var(--v-line-strong);
  }
</style>
