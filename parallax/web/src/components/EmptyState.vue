<script setup lang="ts">
defineProps<{ title: string; detail?: string }>()
</script>

<template>
  <section class="empty" role="status">
    <h2 class="empty__title">{{ title }}</h2>
    <p v-if="detail" class="empty__detail">{{ detail }}</p>
    <slot />
  </section>
</template>

<style scoped>
.empty {
  padding: var(--spacing-200, 32px) var(--spacing-150, 24px);
  border: var(--border-width-base, 1px) dashed var(--border-color-base);
  border-radius: var(--border-radius-base, 2px);
  color: var(--color-subtle);
  text-align: center;
}
.empty__title {
  margin: 0 0 var(--spacing-50, 8px);
  font-family: var(--font-family-serif);
  font-size: 1.25rem;
  font-weight: normal;
  color: var(--color-base);
}
.empty__detail {
  margin: 0 auto;
  max-width: 56ch;
}
</style>
