<script setup lang="ts">
// Atlas: every topic in fi, sv or en and how far apart the editions' articles are. Counts and distances, no verdict.
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { CdxButton, CdxMessage, CdxProgressBar } from '@wikimedia/codex'
import { api, type Atlas, type AtlasTopic } from '../api'
import { navigate } from '../state'
import EmptyState from '../components/EmptyState.vue'

const PAGE = 50
const COVERAGES = [
  { value: '', label: 'Every topic' },
  { value: 'all', label: 'fi, sv and en' },
  { value: 'fi+sv', label: 'fi and sv only' },
  { value: 'fi+en', label: 'fi and en only' },
  { value: 'fi', label: 'fi only' },
] as const
const COLUMNS = [
  { key: 'fi_sv', label: 'fi to sv' },
  { key: 'fi_en', label: 'fi to en' },
  { key: 'sv_en', label: 'sv to en' },
] as const

const coverage = ref('')
const sort = ref('wikidata_id')
const counts = ref<Atlas['counts'] | null>(null)
const topics = ref<AtlasTopic[]>([])
const loading = ref(false)
const error = ref('')
let controller: AbortController | null = null

async function load(append = false) {
  controller?.abort()
  const mine = (controller = new AbortController())
  loading.value = true
  error.value = ''
  try {
    const body = await api.atlas(
      { coverage: coverage.value || undefined, sort: sort.value, limit: PAGE, offset: append ? topics.value.length : 0 },
      { signal: mine.signal },
    )
    counts.value = body.counts
    topics.value = append ? [...topics.value, ...body.topics] : body.topics
  } catch (e) {
    if (!mine.signal.aborted) error.value = (e as Error).message
  } finally {
    if (controller === mine) loading.value = false
  }
}
watch([coverage, sort], () => load(), { immediate: true })
onBeforeUnmount(() => controller?.abort())

const total = computed(() => (counts.value ? Object.values(counts.value).reduce((a, b) => a + b, 0) : 0))
const shown = computed(() => (coverage.value ? (counts.value?.[coverage.value] ?? 0) : total.value))
const n = (x: number) => x.toLocaleString('en-US')
const dist = (x: number | null | undefined) => (x == null ? '' : x.toFixed(2))
const title = (t: AtlasTopic) => t.titles.en ?? t.titles.fi ?? t.titles.sv ?? t.wikidata_id
const ariaSort = (key: string) => (sort.value === key ? 'descending' : 'none')
</script>

<template>
  <section class="atlas" aria-label="Atlas">
    <header>
      <h2 class="atlas__title">Atlas</h2>
      <p class="atlas__lead">
        Every topic with an article in Finnish, Swedish or English. The numbers are the cosine distance between the
        article vectors of two editions: 0 means the articles cover the same ground, larger means they differ more. They
        say how far apart two articles are, not which one is right.
      </p>
    </header>

    <div v-if="counts" class="atlas__filters" role="group" aria-label="Coverage">
      <button
        v-for="c in COVERAGES"
        :key="c.value"
        type="button"
        class="atlas__chip"
        :class="{ 'atlas__chip--on': coverage === c.value }"
        :aria-pressed="coverage === c.value"
        data-testid="atlas-coverage"
        @click="coverage = c.value"
      >
        {{ c.label }} <b>{{ n(c.value ? (counts[c.value] ?? 0) : total) }}</b>
      </button>
    </div>

    <CdxProgressBar v-if="loading && !topics.length" inline aria-label="Loading the atlas" />
    <CdxMessage v-if="error" type="error">{{ error }}</CdxMessage>
    <EmptyState
      v-if="counts && !total && !loading"
      title="The atlas is not loaded yet"
      detail="The atlas of topics in fi, sv and en arrives with the next data release."
    />

    <div v-if="topics.length" class="atlas__scroll">
      <table class="atlas__table" data-testid="atlas-table">
        <thead>
          <tr>
            <th scope="col" :aria-sort="ariaSort('wikidata_id')">
              <button type="button" @click="sort = 'wikidata_id'">Topic</button>
            </th>
            <th scope="col">Editions</th>
            <th v-for="c in COLUMNS" :key="c.key" scope="col" class="atlas__num" :aria-sort="ariaSort(c.key)">
              <button type="button" :data-testid="`atlas-sort-${c.key}`" @click="sort = c.key">
                {{ c.label }}<span aria-hidden="true">{{ sort === c.key ? ' ▼' : '' }}</span>
              </button>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="t in topics" :key="t.wikidata_id" data-testid="atlas-row">
            <th scope="row">
              <a v-if="t.topic_id" href="#" class="atlas__deep" @click.prevent="navigate({ view: 'compare', topic: t.topic_id })">
                {{ title(t) }}
              </a>
              <span v-else>{{ title(t) }}</span>
              <a class="atlas__qid" :href="`https://www.wikidata.org/wiki/${t.wikidata_id}`" target="_blank" rel="noopener">
                {{ t.wikidata_id }}
              </a>
              <span v-if="t.topic_id" class="atlas__tag">in Compare</span>
            </th>
            <td class="atlas__langs">
              <template v-for="lang in ['fi', 'sv', 'en']" :key="lang">
                <a
                  v-if="t.titles[lang]"
                  :href="`https://${lang}.wikipedia.org/wiki/${encodeURIComponent(String(t.titles[lang]).replace(/ /g, '_'))}`"
                  :title="`Open on ${lang}.wikipedia: ${t.titles[lang]}`"
                  target="_blank"
                  rel="noopener"
                >{{ lang }}</a>
              </template>
            </td>
            <td v-for="c in COLUMNS" :key="c.key" class="atlas__num">{{ dist(t.dist[c.key]) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="topics.length < shown" class="atlas__more">
      <CdxButton :disabled="loading" @click="load(true)">Show {{ Math.min(PAGE, shown - topics.length) }} more of {{ n(shown) }}</CdxButton>
    </div>
  </section>
</template>

<style scoped>
.atlas {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-100, 16px);
  max-width: 960px;
}
.atlas p,
.atlas__title {
  margin: 0;
}
.atlas__title {
  font-family: var(--font-family-serif);
  font-size: 1.5rem;
  font-weight: normal;
}
.atlas__lead {
  max-width: 72ch;
  margin-top: var(--spacing-50, 8px) !important;
  color: var(--color-subtle);
}
.atlas__filters {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-50, 8px);
}
.atlas__chip {
  padding: 4px 12px;
  border: 1px solid var(--border-color-base);
  border-radius: 999px;
  background: var(--background-color-base);
  color: var(--color-base);
  font: inherit;
  font-size: var(--font-size-small, 0.875rem);
  cursor: pointer;
}
.atlas__chip b {
  margin-left: 4px;
  font-variant-numeric: tabular-nums;
}
.atlas__chip--on {
  border-color: var(--color-progressive);
  background: var(--background-color-progressive-subtle);
  color: var(--color-progressive);
}
.atlas__scroll {
  overflow-x: auto;
}
.atlas__table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--font-size-small, 0.875rem);
}
.atlas__table th,
.atlas__table td {
  padding: 6px 12px 6px 0;
  border-bottom: 1px solid var(--border-color-subtle);
  text-align: left;
  vertical-align: baseline;
}
.atlas__table thead th {
  white-space: nowrap;
}
.atlas__table thead button {
  padding: 0;
  border: 0;
  background: none;
  color: var(--color-base);
  font: inherit;
  font-weight: bold;
  cursor: pointer;
}
.atlas__table thead th[aria-sort='descending'] button {
  color: var(--color-progressive);
}
.atlas__table tbody th {
  font-weight: normal;
}
.atlas__num {
  text-align: right !important;
  font-variant-numeric: tabular-nums;
}
td.atlas__num {
  font-family: var(--font-family-monospace, monospace);
}
.atlas__qid {
  margin-left: 8px;
  font-family: var(--font-family-monospace, monospace);
  font-size: 0.75rem;
  color: var(--color-subtle);
}
.atlas__tag {
  margin-left: 8px;
  white-space: nowrap;
  padding: 0 6px;
  border-radius: 999px;
  background: var(--background-color-progressive-subtle);
  color: var(--color-progressive);
  font-size: 0.75rem;
}
.atlas__deep {
  font-weight: bold;
}
.atlas__langs a {
  margin-right: 6px;
  font-family: var(--font-family-monospace, monospace);
}
.atlas__more {
  display: flex;
  justify-content: center;
}
</style>
