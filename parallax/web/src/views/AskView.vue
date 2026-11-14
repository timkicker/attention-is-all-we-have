<script setup lang="ts">
// Ask: the sentences of each edition nearest to a question, as the editions stood at the chosen date. Quotes only.
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { CdxButton, CdxField, CdxMessage, CdxProgressBar, CdxTextInput } from '@wikimedia/codex'
import { api, type Ask } from '../api'
import { langDir, langName, shortDate } from '../langs'
import { navigate, state } from '../state'

const EXAMPLES = ['Who fired the shots at Mainila?', 'How many soldiers died in the Winter War?', 'Why did the war end?']

const draft = ref(state.q)
const data = ref<Ask | null>(null)
const loading = ref(false)
const error = ref('')
let controller: AbortController | null = null

async function load() {
  controller?.abort()
  if (!state.q) {
    data.value = null
    return
  }
  const mine = (controller = new AbortController())
  loading.value = true
  error.value = ''
  try {
    data.value = await api.ask({ q: state.q, as_of: state.as_of || undefined }, { signal: mine.signal })
  } catch (e) {
    if (!mine.signal.aborted) error.value = (e as Error).message
  } finally {
    if (controller === mine) loading.value = false
  }
}
watch(() => [state.q, state.as_of], load, { immediate: true })
watch(
  () => state.q,
  (q) => (draft.value = q),
)
onBeforeUnmount(() => controller?.abort())

function submit(q = draft.value) {
  const t = q.trim()
  if (t) navigate({ q: t })
}

const fakeEngine = ref(false)
onMounted(async () => {
  try {
    fakeEngine.value = (await api.health()).engine === 'fake'
  } catch {
    fakeEngine.value = false
  }
})

const editions = computed(() => Object.entries(data.value?.quotes ?? {}))
</script>

<template>
  <section class="ask" aria-label="Ask">
    <header>
      <h2 class="ask__title">Ask the editions</h2>
      <p class="ask__lead">
        Ask a question and see the sentences each edition holds that come closest to it, as the editions stood on the
        chosen date. This page quotes Wikipedia and writes nothing of its own: no summary, no answer.
      </p>
    </header>

    <form class="ask__form" @submit.prevent="submit()">
      <CdxField class="ask__field">
        <CdxTextInput v-model="draft" input-type="search" placeholder="Who fired the shots at Mainila?" aria-label="Question" />
        <template #label>Question</template>
      </CdxField>
      <CdxButton action="progressive" weight="primary" type="submit" :disabled="!draft.trim()">Find quotes</CdxButton>
    </form>
    <p v-if="!state.q" class="ask__examples">
      Try
      <template v-for="(ex, i) in EXAMPLES" :key="ex">
        <a href="#" @click.prevent="submit(ex)">{{ ex }}</a><template v-if="i < EXAMPLES.length - 1"> · </template>
      </template>
    </p>

    <CdxProgressBar v-if="loading" inline aria-label="Finding quotes" />
    <CdxMessage v-if="error" type="error">{{ error }}</CdxMessage>

    <template v-if="data && editions.length">
      <p class="ask__note">
        Nearest sentences on {{ shortDate(data.as_of) }}, by meaning. Near means the sentence talks about something
        similar, not that it answers the question.
      </p>
      <CdxMessage v-if="fakeEngine" type="notice" data-testid="ask-fake">
        This instance runs the test engine, which turns a new question into a random vector. The quotes are real
        sentences but their order means nothing until the real engine runs.
      </CdxMessage>
      <div class="ask__grid">
        <article v-for="[lang, quotes] in editions" :key="lang" class="ask__col" :data-lang="lang" data-testid="ask-edition">
          <h3 class="ask__lang">{{ langName(lang) }} <span>{{ lang }}</span></h3>
          <p v-if="!quotes.length" class="ask__empty">No sentence at this date.</p>
          <figure v-for="(q, i) in quotes" :key="i" class="ask__quote" data-testid="ask-quote">
            <blockquote :lang="lang" :dir="langDir(lang)">{{ q.text }}</blockquote>
            <p v-if="q.gloss && lang !== 'en'" class="ask__gloss" lang="en">
              <span class="ask__gloss-label">machine translation</span>{{ q.gloss }}
            </p>
            <figcaption class="ask__foot">
              <a v-if="q.oldid_url" :href="q.oldid_url" target="_blank" rel="noopener">Open on {{ lang }}.wikipedia</a>
              <span class="ask__dist">distance {{ q.dist.toFixed(2) }}</span>
            </figcaption>
          </figure>
        </article>
      </div>
    </template>
  </section>
</template>

<style scoped>
.ask {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-100, 16px);
}
.ask p,
.ask__title,
.ask__lang {
  margin: 0;
}
.ask__title {
  font-family: var(--font-family-serif);
  font-size: 1.5rem;
  font-weight: normal;
}
.ask__lead {
  max-width: 72ch;
  margin-top: var(--spacing-50, 8px) !important;
  color: var(--color-subtle);
}
.ask__form {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: var(--spacing-75, 12px);
  max-width: 720px;
}
.ask__field {
  flex: 1 1 320px;
  margin: 0 !important;
}
.ask__examples,
.ask__note {
  font-size: var(--font-size-small, 0.875rem);
  color: var(--color-subtle);
}
.ask__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--spacing-75, 12px);
}
.ask__col {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-75, 12px);
  min-width: 0;
}
.ask__lang {
  font-size: 1rem;
  border-bottom: 1px solid var(--border-color-subtle);
  padding-bottom: var(--spacing-25, 4px);
}
.ask__lang span {
  margin-left: var(--spacing-25, 4px);
  font-family: var(--font-family-monospace, monospace);
  font-size: 0.75rem;
  font-weight: normal;
  color: var(--color-subtle);
}
.ask__quote {
  margin: 0;
  padding: var(--spacing-75, 12px);
  border: 1px solid var(--border-color-subtle);
  border-radius: 2px;
  background: var(--background-color-base);
}
.ask__quote blockquote {
  margin: 0;
  font-family: var(--font-family-serif);
  font-size: 0.9375rem;
  line-height: 1.45;
  overflow-wrap: anywhere;
}
.ask__gloss {
  margin-top: var(--spacing-50, 8px) !important;
  color: var(--color-subtle);
  font-size: var(--font-size-small, 0.875rem);
}
.ask__gloss-label {
  display: block;
  font-size: 0.75rem;
  color: var(--color-placeholder);
}
.ask__foot {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 0 var(--spacing-50, 8px);
  margin-top: var(--spacing-50, 8px);
  font-size: var(--font-size-small, 0.875rem);
}
.ask__dist {
  color: var(--color-placeholder);
  font-family: var(--font-family-monospace, monospace);
  font-size: 0.75rem;
}
.ask__empty {
  color: var(--color-subtle);
  font-style: italic;
}
</style>
