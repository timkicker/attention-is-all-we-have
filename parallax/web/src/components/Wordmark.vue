<script setup lang="ts">
// Our own text wordmark: the name in the serif token next to two offset frames, the idea of one object
// seen from two positions. Nothing borrowed from any Wikimedia mark.
</script>

<template>
  <a class="wordmark" href="/compare" aria-label="Parallax, start page">
    <svg class="wordmark__mark" viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
      <rect x="2.5" y="6.5" width="12" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1.5" />
      <rect x="9.5" y="2.5" width="12" height="12" rx="1" fill="currentColor" opacity="0.35" />
    </svg>
    <span class="wordmark__name">Parallax</span>
  </a>
</template>

<style scoped>
.wordmark {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-family-serif);
  font-size: 1.625rem;
  line-height: 1;
  color: var(--color-emphasized);
  text-decoration: none;
}
.wordmark__mark {
  color: var(--color-progressive);
  flex: none;
}
.wordmark:focus-visible {
  outline: 2px solid var(--color-progressive);
  outline-offset: 4px;
}
</style>
