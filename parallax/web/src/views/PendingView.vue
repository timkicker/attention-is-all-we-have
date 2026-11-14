<script setup lang="ts">
// Placeholder for a view that is not built yet: an empty state, never fake data.
import EmptyState from '../components/EmptyState.vue'

defineProps<{ label: string; detail: string }>()
</script>

<template>
  <EmptyState :title="`${label}: no data yet`" :detail="detail" />
</template>
