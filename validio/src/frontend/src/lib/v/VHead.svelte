<script lang="ts">
  /// The page head: crumbs, the h1, facts, then whatever the page puts
  /// under them (lead, question, button). Actions sit on the right. On the
  /// phone a detail page gets a way back above the title instead of crumbs.
  import type { Snippet } from "svelte";
  import { goto } from "$app/navigation";
  import { ChevronLeft } from "@lucide/svelte";
  import { cameFrom } from "@arlen/ui-kit/components/ui/page/history";
  import { chrome, setTitle } from "$lib/chrome.svelte";
  import { nb } from "$lib/format";

  let {
    title,
    crumbs = [],
    here = "",
    back,
    titleId,
    titleTestid,
    morphName,
    facts,
    actions,
    children,
  }: {
    title: string;
    crumbs?: { href: string; label: string }[];
    /** The last crumb, this page, not a link. */
    here?: string;
    back?: { href: string; label: string };
    titleId?: string;
    titleTestid?: string;
    /** view-transition-name for the title: the clicked row's title travels into it (plans/003). */
    morphName?: string;
    facts?: Snippet;
    actions?: Snippet;
    children?: Snippet;
  } = $props();

  $effect(() => setTitle(title));
  $effect(() => {
    chrome.detail = !!back;
    return () => (chrome.detail = false);
  });
  function goBack(e: MouseEvent) {
    if (!back) return;
    e.preventDefault();
    if (cameFrom(back.href)) history.back();
    else goto(back.href);
  }
</script>

{#if chrome.phone && back}
  <a class="back" href={back.href} onclick={goBack}>
    <ChevronLeft size={16} strokeWidth={1.75} aria-hidden="true" />
    <span>{back.label}</span>
  </a>
{/if}

<header class="head" class:list={!back}>
  <div class="head-main">
    {#if crumbs.length}
      <nav class="crumbs" aria-label="Breadcrumb">
        {#each crumbs as c (c.href)}
          <a href={c.href}>{c.label}</a>
          <span class="crumb-sep" aria-hidden="true">/</span>
        {/each}
        <span aria-current="page">{here}</span>
      </nav>
    {/if}
    <h1 class="v-title" id={titleId} data-testid={titleTestid} tabindex="-1" style:view-transition-name={morphName}>{nb(title)}</h1>
    {#if facts}<div class="facts">{@render facts()}</div>{/if}
    {@render children?.()}
  </div>
  {#if actions}
    <div class="head-actions">
      {@render actions()}
    </div>
  {/if}
</header>

<style>
  .head-main {
    min-width: 0;
  }
  .crumb-sep {
    color: var(--v-line-strong);
  }
  .back {
    display: inline-flex;
    align-items: center;
    gap: 2px;
    min-height: 44px;
    margin: -12px 0 4px -4px;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--valio);
    text-decoration: none;
  }
  @media (max-width: 760px) {
    .head.list {
      grid-template-columns: minmax(0, 1fr) auto;
    }
    .head.list .head-main {
      display: contents;
    }
    .head.list :global(h1) {
      grid-column: 1;
      grid-row: 1;
      align-self: center;
    }
    .head.list :global(.facts) {
      grid-column: 1 / -1;
      grid-row: 2;
    }
    .head.list .head-main > :global(:not(h1):not(.facts):not(.crumbs)) {
      grid-column: 1 / -1;
    }
    .head.list .head-actions {
      grid-column: 2;
      grid-row: 1;
    }
    .head-actions {
      padding-bottom: 0;
    }
    .head:not(.list) .head-actions {
      margin-top: 20px;
    }
    .head:not(.list) .head-actions :global([data-slot="button"]) {
      width: 100%;
    }
  }
</style>
