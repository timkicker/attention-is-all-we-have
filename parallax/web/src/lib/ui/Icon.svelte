<script lang="ts">
  // Inline SVG icons from the wireframes: search and calendar. 16px, stroke follows text colour.
  let { name }: { name: 'search' | 'calendar' } = $props()
</script>

<svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
  {#if name === 'search'}
    <circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" />
  {:else}
    <rect x="4" y="5" width="16" height="15" rx="2" /><path d="M4 10h16M9 3v4M15 3v4" />
  {/if}
</svg>
