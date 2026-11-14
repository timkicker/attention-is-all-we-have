<script lang="ts">
  /// A titled block of rows: an h2 with an optional count and an optional link
  /// on the right (Home's "Latest" with "All activity"), then the kit Section
  /// card holding the rows (ActivityRow, ListRow, VStatusRow).
  import type { Snippet } from "svelte";
  import { Section } from "@arlen/ui-kit/components/ui/section";
  import VPill from "$lib/v/VPill.svelte";

  let {
    id,
    title,
    count,
    link,
    children,
  }: {
    /** Used for the heading's id ("h-{id}") and the testid ("section-{id}"). */
    id: string;
    /** Leave out for a card without a heading (a day group under its own head). */
    title?: string;
    /** A number badge after the title, e.g. how many need the owner. */
    count?: number;
    link?: { href: string; label: string };
    children: Snippet;
  } = $props();
</script>

<section class="ls" aria-labelledby={title ? `h-${id}` : undefined} data-testid="section-{id}">
  {#if title}
    <div class="ls-head">
      <h2 class="v-h" id="h-{id}">
        {title}
        {#if count}<VPill count label={String(count)} tone="wait" /><span class="sr-only">, {count}</span>{/if}
      </h2>
      {#if link}<a class="ls-link" href={link.href} id="{id}-link" data-testid="{id}-link">{link.label}</a>{/if}
    </div>
  {/if}
  <Section class="v-card">
    {@render children()}
  </Section>
</section>

<style>
  .ls {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .ls-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 16px;
  }
  .ls-head h2 {
    display: inline-flex;
    align-items: center;
    gap: 8px;
  }
  .ls-link {
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-muted);
  }
  .ls-link:hover {
    color: var(--v-fg);
  }
</style>
