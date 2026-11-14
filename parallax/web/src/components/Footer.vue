<script setup lang="ts">
import { FOOTER_TEXT } from '../copy'
</script>

<template>
  <footer class="site-footer">
    <p>{{ FOOTER_TEXT }}</p>
    <p class="site-footer__meta">
      Evidence, not edits. Parallax only reads.
      <a href="https://creativecommons.org/licenses/by-sa/4.0/" rel="license noopener" target="_blank">CC BY-SA 4.0</a>
      ·
      <a href="https://github.com/timkicker/attention-is-all-we-have" rel="noopener" target="_blank">Source code (MIT)</a>
    </p>
  </footer>
</template>

<style scoped>
.site-footer {
  margin-top: var(--spacing-300, 48px);
  padding: var(--spacing-100, 16px) 0 var(--spacing-200, 32px);
  border-top: var(--border-width-base, 1px) solid var(--border-color-subtle);
  color: var(--color-subtle);
  font-size: var(--font-size-small, 0.875rem);
  line-height: var(--line-height-small, 1.5);
}
.site-footer p {
  margin: 0 0 var(--spacing-50, 8px);
  max-width: 72ch;
}
.site-footer a {
  color: var(--color-progressive);
}
</style>
