<script setup lang="ts">
// Time: the slider cuts every edition at one instant; Compare follows it and the chosen claim shows its lives.
import { computed } from 'vue'
import type { Topic } from '../api'
import { navigate, state } from '../state'
import { exactDates } from '../snaps'
import DateSlider from '../components/DateSlider.vue'
import ClaimTimeline from '../components/ClaimTimeline.vue'
import EmptyState from '../components/EmptyState.vue'
import CompareView from './CompareView.vue'

defineProps<{ topics: Topic[] }>()

const asOf = computed({ get: () => state.as_of, set: (v: string) => navigate({ as_of: v }, true) })
</script>

<template>
  <section class="time-view" aria-label="Time">
    <div class="time-view__slider">
      <DateSlider v-model="asOf" :exact="exactDates" />
    </div>
    <ClaimTimeline v-if="state.claim" :claim-key="state.claim" :as-of="state.as_of" />
    <EmptyState
      v-else
      title="Pick a sentence below"
      detail="Its life in every edition appears here. Then drag the date and watch the editions change."
    />
    <CompareView :topics="topics" :debounce-ms="150" @open="(lang, cell) => navigate({ claim: `${lang}:${cell.page_id}:${cell.h}` })" />
  </section>
</template>

<style scoped>
.time-view {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-150, 24px);
}
.time-view__slider {
  position: sticky;
  top: 0;
  z-index: 2;
  background: var(--background-color-base);
  padding: var(--spacing-50, 8px) 0;
}
</style>
