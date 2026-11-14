<script setup lang="ts">
// Dropped here, alive there: sentences one edition removed while other editions still state them,
// and the same list over every revision of the Finnish edition.
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { CdxButton, CdxField, CdxMessage, CdxProgressBar, CdxSelect } from '@wikimedia/codex'
import { api, type Dropped, type DroppedRow, type Topic } from '../api'
import { langName } from '../langs'
import { state } from '../state'
import DroppedCard from '../components/DroppedCard.vue'
import EmptyState from '../components/EmptyState.vue'

const props = defineProps<{ topics: Topic[] }>()

const PAGE = 25
const mode = ref<'topic' | 'fi'>('topic')
const lang = ref('')
const reason = ref('')
const minDays = ref('365')
const data = ref<Dropped | null>(null)
const rows = ref<DroppedRow[]>([])
const loading = ref(false)
const error = ref('')
let controller: AbortController | null = null

const topic = computed(() => props.topics.find((t) => t.topic_id === state.topic))
const modeItems = computed(() => [
  { value: 'topic', label: `${topic.value?.label_en ?? state.topic}, every edition` },
  { value: 'fi', label: 'Finnish edition, every article' },
])
const langItems = computed(() => [
  { value: '', label: 'Every edition' },
  ...(topic.value?.editions ?? []).map((e) => ({ value: e.lang, label: `${langName(e.lang)} (${e.lang})` })),
])
const reasonItems = [
  { value: '', label: 'Any edit comment' },
  { value: 'unsourced', label: 'Comment says no source (lähteetön)' },
  { value: 'error', label: 'Comment mentions a correction' },
  { value: 'speculation', label: 'Comment mentions speculation' },
  { value: 'other', label: 'Other comment' },
  { value: 'none', label: 'No comment' },
]
const daysItems = [
  { value: '0', label: 'Any time' },
  { value: '365', label: 'At least 1 year' },
  { value: '1095', label: 'At least 3 years' },
]

async function load(offset = 0) {
  controller?.abort()
  const mine = (controller = new AbortController())
  loading.value = true
  error.value = ''
  try {
    const params =
      mode.value === 'topic'
        ? { topic: state.topic, lang: lang.value || undefined, min_days: Number(minDays.value) }
        : { lang: 'fi', reason: reason.value || undefined, min_days: Number(minDays.value) }
    const body = await api.dropped({ ...params, offset, limit: PAGE }, { signal: mine.signal })
    data.value = body
    rows.value = offset ? [...rows.value, ...(body.rows as DroppedRow[])] : (body.rows as DroppedRow[])
  } catch (e) {
    if (mine.signal.aborted) return
    error.value = (e as Error).message
  } finally {
    if (controller === mine) loading.value = false
  }
}

watch([() => state.topic, mode, lang, reason, minDays], () => load(0), { immediate: true })
onBeforeUnmount(() => controller?.abort())

const more = computed(() => (data.value ? data.value.total - rows.value.length : 0))
const scale = computed(() => data.value?.scale)
const n = (x: number) => x.toLocaleString('en-US')
</script>

<template>
  <section class="dropped" aria-label="Dropped here, alive there">
    <header class="dropped__intro">
      <h2 class="dropped__title">Dropped here, alive there</h2>
      <p class="dropped__lead">
        Sentences one edition stopped saying while other editions still state the same claim. Each card shows when the
        sentence was removed, the edit comment and a link to the last revision that had it. A person decides what it
        means.
      </p>
      <p v-if="scale && scale.fi_lives" class="dropped__scale" data-testid="fi-scale">
        Finnish edition: <b>{{ n(scale.fi_lives) }}</b> sentence lives from {{ n(scale.fi_revisions) }} revisions,
        {{ n(scale.fi_dead) }} of them removed, {{ n(scale.fi_dead_1y) }} after at least a year.
      </p>
    </header>

    <div class="dropped__filters">
      <CdxField class="dropped__field">
        <template #label>List</template>
        <CdxSelect v-model:selected="mode" :menu-items="modeItems" />
      </CdxField>
      <CdxField v-if="mode === 'topic'" class="dropped__field">
        <template #label>Edition that dropped it</template>
        <CdxSelect v-model:selected="lang" :menu-items="langItems" />
      </CdxField>
      <CdxField v-else class="dropped__field">
        <template #label>Edit comment</template>
        <CdxSelect v-model:selected="reason" :menu-items="reasonItems" />
      </CdxField>
      <CdxField class="dropped__field">
        <template #label>Stated for</template>
        <CdxSelect v-model:selected="minDays" :menu-items="daysItems" />
      </CdxField>
    </div>

    <CdxProgressBar v-if="loading" inline aria-label="Loading dropped sentences" />
    <CdxMessage v-if="error" type="error">{{ error }}</CdxMessage>
    <p v-if="data && rows.length" class="dropped__count">
      {{ n(data.total) }} sentence{{ data.total === 1 ? '' : 's' }}, longest stated first.
    </p>
    <EmptyState
      v-if="data && !rows.length && !loading && !error"
      :title="mode === 'topic' ? 'No dropped sentence with a match yet' : 'No Finnish sentence lives loaded yet'"
      :detail="
        mode === 'topic'
          ? 'A sentence is listed once the judge pairs it with a sentence another edition states today.'
          : 'The Finnish lives of every article arrive with the next data release.'
      "
    />
    <div class="dropped__list">
      <DroppedCard v-for="r in rows" :key="`${r.lang}:${r.page_id}:${r.h}`" :row="r" />
    </div>
    <div v-if="more > 0" class="dropped__more">
      <CdxButton :disabled="loading" @click="load(rows.length)">Show {{ Math.min(more, PAGE) }} more of {{ n(more) }}</CdxButton>
    </div>
  </section>
</template>

<style scoped>
.dropped {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-100, 16px);
}
.dropped__intro p,
.dropped__title {
  margin: 0;
}
.dropped__title {
  font-family: var(--font-family-serif);
  font-size: 1.5rem;
  font-weight: normal;
}
.dropped__lead {
  max-width: 70ch;
  margin-top: var(--spacing-50, 8px) !important;
  color: var(--color-subtle);
}
.dropped__scale {
  margin-top: var(--spacing-50, 8px) !important;
}
.dropped__filters {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-75, 12px) var(--spacing-150, 24px);
}
.dropped__field {
  margin: 0;
}
.dropped__count {
  margin: 0;
  color: var(--color-subtle);
}
.dropped__list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-100, 16px);
  max-width: 960px;
}
.dropped__more {
  text-align: center;
}
</style>
