<script setup lang="ts">
// Side drawer over Compare with the timeline of the clicked sentence. Esc or the close button shuts it.
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { CdxButton } from '@wikimedia/codex'
import ClaimTimeline from './ClaimTimeline.vue'

defineProps<{ claimKey: string; asOf: string }>()
const emit = defineEmits<{ close: [] }>()
const closeBtn = ref<InstanceType<typeof CdxButton> | null>(null)

function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('close')
}
onMounted(async () => {
  window.addEventListener('keydown', onKey)
  await nextTick()
  ;(closeBtn.value?.$el as HTMLElement | undefined)?.focus()
})
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <div class="drawer" role="dialog" aria-modal="false" aria-label="Timeline of the sentence">
    <div class="drawer__bar">
      <span class="drawer__title">Timeline</span>
      <CdxButton ref="closeBtn" weight="quiet" @click="emit('close')">Close</CdxButton>
    </div>
    <ClaimTimeline :claim-key="claimKey" :as-of="asOf" />
  </div>
</template>

<style scoped>
.drawer {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  z-index: 10;
  width: min(720px, 100vw);
  overflow-y: auto;
  padding: var(--spacing-100, 16px) var(--spacing-150, 24px) var(--spacing-200, 32px);
  border-left: var(--border-width-base, 1px) solid var(--border-color-base);
  background: var(--background-color-base);
  box-shadow: var(--box-shadow-drop-xx-large, 0 20px 48px rgba(0, 0, 0, 0.2));
}
.drawer__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--spacing-75, 12px);
}
.drawer__title {
  font-family: var(--font-family-serif);
  font-size: 1.25rem;
}
@media (max-width: 720px) {
  .drawer {
    padding: var(--spacing-75, 12px) var(--spacing-100, 16px);
  }
}
</style>
