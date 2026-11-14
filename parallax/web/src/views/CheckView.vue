<script setup lang="ts">
// Check an answer: paste an AI answer or pick a recorded one, see per claim what each edition says.
import { computed, onMounted, ref, watch } from 'vue'
import { CdxButton, CdxField, CdxMessage, CdxProgressBar, CdxSelect, CdxTextArea } from '@wikimedia/codex'
import { api, type Check } from '../api'
import { shortDate } from '../langs'
import { navigate, state } from '../state'
import ClaimLabels from '../components/ClaimLabels.vue'
import EmptyState from '../components/EmptyState.vue'

const recorded = ref<{ value: string; label: string; description: string }[]>([])
const text = ref('')
const run = ref<Check | null>(null)
const loading = ref(false)
const error = ref('')
const agreement = ref<string>('')

onMounted(async () => {
  try {
    const body = await api.checkRecorded()
    recorded.value = body.runs.map((r) => ({
      value: r.run_id,
      label: r.question ?? 'Answer without a question',
      description: [r.answer_model, r.answer_date].filter(Boolean).join(', '),
    }))
  } catch {
    recorded.value = []
  }
  try {
    const s = (await api.stats()).stats as Record<string, unknown>
    const ev = s.judge_eval as { accuracy?: number; kappa?: number; n?: number } | undefined
    if (ev?.accuracy != null)
      agreement.value = `It agrees with our hand labels on ${Math.round(ev.accuracy * 100)} % of ${ev.n ?? 'the'} gold pairs${
        ev.kappa != null ? ` (Cohen's kappa ${ev.kappa.toFixed(2)})` : ''
      }.`
  } catch {
    agreement.value = ''
  }
})

const picked = computed({
  get: () => (run.value?.source === 'recorded' ? run.value.run_id : state.run && run.value === null ? state.run : ''),
  set: (v: string) => navigate({ run: v }),
})

async function guard(fn: () => Promise<Check>) {
  loading.value = true
  error.value = ''
  try {
    run.value = await fn()
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

let loadedKey = ''
watch(
  () => [state.run, state.as_of],
  () => {
    const key = `${state.run}@${state.as_of}`
    if (key === loadedKey) return // the run was just posted, no need to fetch it again
    loadedKey = key
    if (state.run) guard(() => api.checkRun(state.run, state.as_of || undefined))
    else run.value = null
  },
  { immediate: true },
)

async function submit() {
  if (!text.value.trim()) return
  await guard(() => api.check({ text: text.value, as_of: state.as_of || undefined }))
  if (run.value) {
    loadedKey = `${run.value.run_id}@${state.as_of}`
    navigate({ run: run.value.run_id }, true)
  }
}

const judge = computed(() => {
  for (const c of run.value?.claims ?? [])
    for (const v of Object.values(c.per_lang)) for (const e of v.evidence) if (e.verdict?.model) return e.verdict.model
  return null
})
const note = computed(() => {
  const r = run.value
  if (!r) return ''
  const when = r.answer_date ? `, ${shortDate(r.answer_date)}` : ''
  return r.source === 'recorded' ? `Recorded answer from ${r.answer_model ?? 'an unknown model'}${when}` : 'Live check'
})
</script>

<template>
  <section class="check" aria-label="Check an answer">
    <header class="check__intro">
      <h2 class="check__title">Check an answer</h2>
      <p class="check__lead">
        Paste what an AI assistant said about the topic. Parallax splits it into claims and shows, edition by edition,
        whether Wikipedia says it, stopped saying it, differs or has no such sentence, with the sentences as evidence.
      </p>
    </header>

    <div class="check__inputs">
      <CdxField class="check__pick">
        <template #label>Recorded answer</template>
        <template #help-text>Checked once ahead of time, so it works offline.</template>
        <CdxSelect
          v-model:selected="picked"
          :menu-items="recorded"
          :disabled="!recorded.length"
          :default-label="recorded.length ? 'Pick an answer' : 'No recorded answers yet'"
        />
      </CdxField>
      <CdxField class="check__paste">
        <template #label>Or paste an answer</template>
        <CdxTextArea v-model="text" :rows="4" placeholder="The Shelling of Mainila on 26 November 1939 was ..." />
      </CdxField>
      <CdxButton action="progressive" weight="primary" :disabled="loading || !text.trim()" @click="submit">
        Check this answer
      </CdxButton>
    </div>

    <CdxProgressBar v-if="loading" inline aria-label="Checking the answer" />
    <CdxMessage v-if="error" type="error">{{ error }}</CdxMessage>

    <template v-if="run && !loading">
      <div class="check__note" data-testid="check-note">
        <p>
          <b>{{ note }}</b>, labelled on {{ run.as_of ? shortDate(run.as_of) : 'today' }}.
          <template v-if="judge">Claims are matched to sentences by vector distance and judged by <b>{{ judge }}</b>.</template>
          {{ agreement }}
        </p>
        <p v-if="run.question" class="check__question">Question: {{ run.question }}</p>
      </div>
      <EmptyState v-if="!run.claims.length" title="No claims found" detail="The answer has no sentence long enough to check." />
      <ClaimLabels v-for="c in run.claims" :key="c.idx" :claim="c" />
    </template>
    <EmptyState
      v-else-if="!loading && !error"
      title="Nothing checked yet"
      detail="Pick a recorded answer or paste one. Each claim gets one label per edition."
    />
  </section>
</template>

<style scoped>
.check {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-100, 16px);
  max-width: 960px;
}
.check p,
.check__title {
  margin: 0;
}
.check__title {
  font-family: var(--font-family-serif);
  font-size: 1.5rem;
  font-weight: normal;
}
.check__lead {
  max-width: 70ch;
  margin-top: var(--spacing-50, 8px) !important;
  color: var(--color-subtle);
}
.check__inputs {
  display: grid;
  grid-template-columns: minmax(300px, 1fr) minmax(260px, 1.4fr) auto;
  align-items: end;
  gap: var(--spacing-100, 16px);
}
.check__pick,
.check__paste {
  margin: 0;
}
.check__note {
  padding: var(--spacing-75, 12px) var(--spacing-100, 16px);
  border-radius: var(--border-radius-base, 2px);
  background: var(--background-color-neutral-subtle);
}
.check__question {
  margin-top: var(--spacing-25, 4px) !important;
  color: var(--color-subtle);
}
@media (max-width: 720px) {
  .check__inputs {
    grid-template-columns: 1fr;
  }
}
</style>
