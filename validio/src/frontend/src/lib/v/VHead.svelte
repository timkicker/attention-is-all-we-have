<script lang="ts">
  /// halbat's page head: crumbs, h1, facts, then whatever the page puts under
  /// them (lead, question, button). Actions and the ⋯ sit top right. On the
  /// phone a detail page gets the sticky header with the way back instead.
  import type { Snippet } from "svelte";
  import { goto } from "$app/navigation";
  import { ChevronLeft, ChevronRight } from "@lucide/svelte";
  import { cameFrom } from "@arlen/ui-kit/components/ui/page/history";
  import { chrome, setTitle } from "$lib/chrome.svelte";
  import { session } from "$lib/owner.svelte";
  import { nb } from "$lib/format";
  import VMenu from "./VMenu.svelte";

  let {
    title,
    crumbs = [],
    here = "",
    back,
    menu = true,
    titleId,
    titleTestid,
    facts,
    actions,
    children,
  }: {
    title: string;
    crumbs?: { href: string; label: string }[];
    /** The last crumb, this page, not a link. */
    here?: string;
    back?: { href: string; label: string };
    menu?: boolean;
    titleId?: string;
    titleTestid?: string;
    facts?: Snippet;
    actions?: Snippet;
    children?: Snippet;
  } = $props();

  $effect(() => setTitle(title));
  $effect(() => {
    chrome.detail = !!back;
    return () => (chrome.detail = false);
  });
  // The ⋯ holds only the demo controls: demo accounts only. On the phone a list
  // page's ⋯ sits in the layout's header line.
  const showMenu = $derived(menu && !!session.account?.isDemo);

  function goBack(e: MouseEvent) {
    if (!back) return;
    e.preventDefault();
    if (cameFrom(back.href)) history.back();
    else goto(back.href);
  }
</script>

{#if chrome.phone && back}
  <div class="kopfleiste">
    <a class="kl-back" href={back.href} onclick={goBack} aria-label="Back to {back.label}">
      <ChevronLeft size={20} strokeWidth={1.75} aria-hidden="true" />
    </a>
    <span class="kl-name" aria-hidden="true">{back.label}</span>
    <span class="grow"></span>
    {#if showMenu}<VMenu />{/if}
  </div>
{/if}

<header class="head" class:list={!back}>
  <div class="head-main">
    {#if crumbs.length}
      <nav class="crumbs" aria-label="Breadcrumb">
        {#each crumbs as c (c.href)}
          <a href={c.href}>{c.label}</a>
          <ChevronRight size={12} strokeWidth={1.75} aria-hidden="true" class="crumb-sep" />
        {/each}
        <span aria-current="page">{here}</span>
      </nav>
    {/if}
    <h1 class="v-title" id={titleId} data-testid={titleTestid}>{nb(title)}</h1>
    {#if facts}<div class="facts">{@render facts()}</div>{/if}
    {@render children?.()}
  </div>
  {#if actions || (showMenu && !chrome.phone)}
    <div class="head-actions">
      {@render actions?.()}
      {#if showMenu && !chrome.phone}<span class="head-menu"><VMenu /></span>{/if}
    </div>
  {/if}
</header>


<style>
  .head-main {
    min-width: 0;
  }
  .head :global(.crumb-sep) {
    opacity: 0.5;
  }
  /* The menu's sheet renders inside this sticky bar; lift the bar while it is open so the sheet is on top. */
  .kopfleiste:has(:global(.dialog-backdrop)) {
    z-index: 60;
  }
  .kopfleiste {
    position: sticky;
    top: 0;
    z-index: 15;
    display: flex;
    align-items: center;
    height: calc(48px + env(safe-area-inset-top));
    padding: env(safe-area-inset-top) 16px 0 8px;
    margin: -8px -16px 16px;
    background: var(--v-app);
    border-bottom: 1px solid var(--v-line);
  }
  .kl-back {
    display: grid;
    place-items: center;
    align-self: stretch;
    width: 44px;
    color: var(--v-fg);
    border-radius: var(--radius-button);
  }
  .kl-name {
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-muted);
  }
  .grow {
    flex: 1;
  }
  .kopfleiste :global(.menu-btn) {
    width: 44px;
    height: 44px;
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
      margin: 0;
    }
    .head.list :global(.facts) {
      grid-column: 1 / -1;
      grid-row: 2;
      margin-top: 4px;
    }
    .head.list .head-actions {
      grid-column: 2;
      grid-row: 1;
    }
    .head:not(.list) .head-actions {
      margin-top: 16px;
    }
    .head:not(.list) .head-actions :global([data-slot="button"]) {
      width: 100%;
    }
    .head-actions :global(.menu-btn) {
      width: 44px;
      height: 44px;
    }
  }
</style>
