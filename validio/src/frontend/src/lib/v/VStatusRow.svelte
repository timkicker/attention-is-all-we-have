<script lang="ts">
  /// halbat's status row in a card: the pill in a 128 px column (kept empty
  /// when a row has none, so titles line up), the title, a sub, and the
  /// right column. With `href` the whole row is one link.
  import type { Snippet } from "svelte";
  import { ChevronRight } from "@lucide/svelte";
  import type { Pill } from "$lib/v";
  import VPill from "./VPill.svelte";

  let {
    pill,
    title,
    sub,
    subTestid,
    end,
    href,
    testid,
    id,
    more,
    right,
    middle,
  }: {
    pill?: Pill | null;
    title: string;
    sub?: string;
    subTestid?: string;
    end?: string;
    href?: string;
    testid?: string;
    id?: string;
    /** Under the sub: a fold, a line, a code field. */
    more?: Snippet;
    /** The right column, when it is more than a word. */
    right?: Snippet;
    /** Between the title and the right column (the spark). */
    middle?: Snippet;
  } = $props();
</script>

<svelte:element this={href ? "a" : "div"} class="v-row" class:has-mid={!!middle} {href} data-testid={testid} {id}>
  <span class="v-row-lead">{#if pill}<VPill label={pill.label} tone={pill.tone} />{/if}</span>
  <span class="v-row-main">
    <span class="v-row-title">{title}</span>
    {#if sub}<span class="v-row-sub" data-testid={subTestid} id={subTestid}>{sub}</span>{/if}
    {#if more}<span class="v-row-more">{@render more()}</span>{/if}
  </span>
  {#if middle}<span class="v-row-mid">{@render middle()}</span>{/if}
  <span class="v-row-end">
    {#if right}{@render right()}{:else if end}<span class="num">{end}</span>{/if}
    {#if href}<ChevronRight class="go" size={16} strokeWidth={1.75} aria-hidden="true" />{/if}
  </span>
</svelte:element>

<style>
  .v-row-main {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }
  .v-row-sub {
    display: block;
  }
  .v-row-more {
    display: block;
    margin-top: 4px;
  }
  .v-row.has-mid {
    grid-template-columns: 128px minmax(0, 1fr) auto auto;
  }
  .v-row-mid {
    align-self: start;
  }
  @media (max-width: 760px) {
    .v-row.has-mid {
      grid-template-columns: minmax(0, 1fr) auto;
    }
    .v-row-mid {
      grid-row: 3;
      grid-column: 1 / -1;
    }
  }
</style>
