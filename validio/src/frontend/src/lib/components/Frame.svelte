<script lang="ts">
  /// The one page frame every single-column page shares, so a page title never
  /// moves when the sidebar changes page: left-aligned, the same padding and
  /// the same h1 everywhere. The request pane uses the same inset and heading
  /// size. `narrow` keeps a form page (approve) at form width, from the same
  /// left edge. On the phone a top-level page leaves its name to the bar and
  /// keeps the heading for screen readers only.
  import type { Snippet } from "svelte";
  import { chrome } from "$lib/chrome.svelte";

  let {
    title,
    titleId,
    titleTestid,
    top = false,
    narrow = false,
    head,
    children,
  }: {
    title: string;
    titleId?: string;
    titleTestid?: string;
    /// A page the sidebar opens directly (not a detail page).
    top?: boolean;
    narrow?: boolean;
    /// Under the title: the facts line, a source line.
    head?: Snippet;
    children?: Snippet;
  } = $props();
</script>

<div class="frame" class:narrow>
  <header class="head">
    <h1 class="title" class:sr-only={top && chrome.phone} id={titleId} data-testid={titleTestid}>{title}</h1>
    {@render head?.()}
  </header>
  {@render children?.()}
</div>

<style>
  .frame {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
    max-width: var(--frame-width);
    padding: var(--frame-pad-top) var(--frame-pad-x) 4rem;
  }
  .narrow {
    max-width: calc(32rem + 2 * var(--frame-pad-x));
  }
  .head {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .title {
    margin: 0;
    font-size: var(--text-xl);
    font-weight: 600;
    line-height: 1.25;
    letter-spacing: -0.01em;
    text-wrap: balance;
  }
</style>
