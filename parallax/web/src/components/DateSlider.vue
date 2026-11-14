<script setup lang="ts">
// The date slider: 1 January of every year from 2003 to today plus the exact dates of edits in the data.
import { computed } from 'vue'
import { shortDate } from '../langs'
import { nearestIndex, sliderPoints } from '../timeaxis'

const props = defineProps<{ modelValue: string; exact: string[] }>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

const points = computed(() => sliderPoints(props.exact))
const index = computed(() => nearestIndex(points.value, props.modelValue))
const label = computed(() => {
  const p = points.value[index.value]
  return p ? shortDate(p) : 'today'
})
const isExact = computed(() => {
  const p = points.value[index.value]
  return !!p && !p.endsWith('-01-01')
})
const exactMarks = computed(() =>
  points.value
    .filter((p) => p && !p.endsWith('-01-01'))
    .map((p) => ({ date: p, left: (points.value.indexOf(p) / (points.value.length - 1)) * 100 })),
)

function onInput(e: Event) {
  const i = Number((e.target as HTMLInputElement).value)
  emit('update:modelValue', points.value[i] ?? '')
}
</script>

<template>
  <div class="date-slider">
    <div class="date-slider__readout" aria-live="polite">
      <span class="date-slider__label">As of</span>
      <span class="date-slider__date" data-testid="slider-date">{{ label }}</span>
      <span v-if="isExact" class="date-slider__exact">exact date of an edit</span>
    </div>
    <div class="date-slider__track">
      <input
        type="range"
        class="date-slider__input"
        min="0"
        :max="points.length - 1"
        step="1"
        :value="index"
        :aria-valuetext="label"
        aria-label="Date to cut every edition at"
        @input="onInput"
      />
      <span
        v-for="m in exactMarks"
        :key="m.date"
        class="date-slider__dot"
        :style="{ left: `${m.left}%` }"
        :title="`edit on ${shortDate(m.date)}`"
      />
    </div>
    <div class="date-slider__ticks" aria-hidden="true">
      <span>{{ points[0].slice(0, 4) }}</span>
      <span>{{ points[Math.floor(points.length / 2)]?.slice(0, 4) }}</span>
      <span>today</span>
    </div>
  </div>
</template>

<style scoped>
.date-slider {
  padding: var(--spacing-75, 12px) var(--spacing-100, 16px);
  border: var(--border-width-base, 1px) solid var(--border-color-subtle);
  border-radius: var(--border-radius-base, 2px);
  background: var(--background-color-neutral-subtle);
}
.date-slider__readout {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: var(--spacing-50, 8px);
}
.date-slider__label {
  color: var(--color-subtle);
}
.date-slider__date {
  font-family: var(--font-family-serif);
  font-size: 1.5rem;
  color: var(--color-emphasized);
}
.date-slider__exact {
  font-size: var(--font-size-small, 0.875rem);
  color: var(--color-warning);
}
.date-slider__track {
  position: relative;
}
.date-slider__input {
  width: 100%;
  margin: var(--spacing-50, 8px) 0 0;
  accent-color: var(--color-progressive);
  cursor: pointer;
}
.date-slider__dot {
  position: absolute;
  top: 0;
  width: 6px;
  height: 6px;
  margin-left: -3px;
  border-radius: 50%;
  background: var(--color-warning);
  pointer-events: none;
}
.date-slider__ticks {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  color: var(--color-subtle);
}
</style>
