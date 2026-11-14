<script setup lang="ts">
// Sources: what each edition cites at the chosen date, by ISBN group and web domain. Counts only, no verdict.
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { CdxMessage, CdxProgressBar } from '@wikimedia/codex'
import { api, type SourceEdition, type Sources } from '../api'
import { ISBN_NAMES, isbnShares, mostly } from '../isbn'
import { langName, shortDate } from '../langs'
import { state } from '../state'
import EmptyState from '../components/EmptyState.vue'

const data = ref<Sources | null>(null)
const loading = ref(false)
const error = ref('')
let controller: AbortController | null = null

async function load() {
  controller?.abort()
  const mine = (controller = new AbortController())
  loading.value = true
  error.value = ''
  try {
    data.value = await api.sources({ topic: state.topic, as_of: state.as_of || undefined }, { signal: mine.signal })
  } catch (e) {
    if (!mine.signal.aborted) error.value = (e as Error).message
  } finally {
    if (controller === mine) loading.value = false
  }
}
watch(() => [state.topic, state.as_of], load, { immediate: true })
onBeforeUnmount(() => controller?.abort())

const editions = computed(() => (data.value?.editions ?? []) as SourceEdition[])
const groupsUsed = computed(() => {
  const seen = new Set(editions.value.flatMap((e) => isbnShares(e.isbn).map((s) => s.group)))
  return Object.keys(ISBN_NAMES).filter((g) => seen.has(g))
})
const isbnTotal = (e: SourceEdition) => Object.values(e.isbn).reduce((a, b) => a + b, 0)
const topDomains = (e: SourceEdition) => Object.entries(e.domains).sort((a, b) => b[1] - a[1]).slice(0, 5)
const pct = (x: number) => `${Math.round(x * 100)} %`

function caption(e: SourceEdition): string {
  const m = mostly(e.isbn)
  const total = isbnTotal(e)
  if (!total) return 'no ISBN in its references'
  if (!m) return `${total} ISBNs, no group above half`
  return `cites mostly ${ISBN_NAMES[m.group] ?? m.group} books (${m.n} of ${m.total} ISBNs)`
}
</script>

<template>
  <section class="sources" aria-label="Sources">
    <header>
      <h2 class="sources__title">Sources</h2>
      <p class="sources__lead">
        What each edition cites on {{ data?.as_of ? shortDate(data.as_of) : 'the chosen date' }}: the books in its
        references by ISBN group (the publisher's country or language area) and the web domains it links most. These
        are counts of references, not a judgement of them.
      </p>
    </header>

    <CdxProgressBar v-if="loading" inline aria-label="Loading sources" />
    <CdxMessage v-if="error" type="error">{{ error }}</CdxMessage>
    <EmptyState
      v-if="data && !editions.length && !loading"
      title="No reference counts for this date"
      detail="Reference counts per revision arrive with the next data release, or the editions had no revision yet at this date."
    />

    <template v-if="editions.length">
      <ul class="sources__legend" aria-label="ISBN groups">
        <li v-for="g in groupsUsed" :key="g">
          <span class="sources__swatch" :class="`isbn--${g}`" />{{ ISBN_NAMES[g] }}<span v-if="g !== 'other'" class="sources__code">{{ g }}</span>
        </li>
      </ul>

      <div class="sources__rows">
        <article v-for="e in editions" :key="e.lang" class="sources__row" :data-lang="e.lang" data-testid="sources-edition">
          <div class="sources__name">
            <b>{{ langName(e.lang) }}</b>
            <span class="sources__meta">
              {{ e.refs.toLocaleString('en-US') }} references,
              <a :href="`https://${e.lang}.wikipedia.org/w/index.php?oldid=${e.rev_id}`" target="_blank" rel="noopener">
                revision{{ e.rev_ts ? ` of ${shortDate(e.rev_ts)}` : '' }}
              </a>
            </span>
          </div>
          <div
            class="sources__bar"
            role="img"
            data-testid="isbn-bar"
            :aria-label="`${langName(e.lang)}: ${isbnShares(e.isbn).map((s) => `${ISBN_NAMES[s.group]} ${s.n}`).join(', ') || 'no ISBNs'}`"
          >
            <span
              v-for="s in isbnShares(e.isbn)"
              :key="s.group"
              class="sources__seg"
              :class="`isbn--${s.group}`"
              :style="{ flexGrow: s.n }"
              :title="`${ISBN_NAMES[s.group]}: ${s.n} of ${isbnTotal(e)} ISBNs (${pct(s.share)})`"
            />
            <span v-if="!isbnTotal(e)" class="sources__none">no ISBNs</span>
          </div>
          <p class="sources__caption">{{ caption(e) }}</p>
          <p v-if="topDomains(e).length" class="sources__domains">
            Links most to
            <template v-for="([d, n], i) in topDomains(e)" :key="d">
              <span class="sources__domain">{{ d }}</span> {{ n }}<template v-if="i < topDomains(e).length - 1">, </template>
            </template>
          </p>
        </article>
      </div>

      <details class="sources__table">
        <summary>Show the counts as a table</summary>
        <table>
          <thead>
            <tr>
              <th scope="col">Edition</th>
              <th scope="col">References</th>
              <th v-for="g in groupsUsed" :key="g" scope="col">{{ g === 'other' ? 'Other' : g }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="e in editions" :key="e.lang">
              <th scope="row">{{ e.lang }}</th>
              <td>{{ e.refs }}</td>
              <td v-for="g in groupsUsed" :key="g">{{ isbnShares(e.isbn).find((s) => s.group === g)?.n ?? 0 }}</td>
            </tr>
          </tbody>
        </table>
      </details>
    </template>
  </section>
</template>

<style scoped>
.sources {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-150, 24px);
  max-width: 960px;
  /* ISBN group colours: fixed order of the categorical palette, light then dark steps */
  --isbn-FI: #2a78d6;
  --isbn-SE: #eb6834;
  --isbn-DE: #1baf7a;
  --isbn-EN: #eda100;
  --isbn-RU: #e87ba4;
  --isbn-EE: #008300;
  --isbn-UA: #6250d6;
  --isbn-other: #8a8a85;
}
@media (prefers-color-scheme: dark) {
  .sources {
    --isbn-FI: #3987e5;
    --isbn-SE: #d95926;
    --isbn-DE: #199e70;
    --isbn-EN: #c98500;
    --isbn-RU: #d55181;
    --isbn-EE: #008300;
    --isbn-UA: #9085e9;
    --isbn-other: #77776f;
  }
}
.sources p,
.sources__title {
  margin: 0;
}
.sources__title {
  font-family: var(--font-family-serif);
  font-size: 1.5rem;
  font-weight: normal;
}
.sources__lead {
  max-width: 72ch;
  margin-top: var(--spacing-50, 8px) !important;
  color: var(--color-subtle);
}
.sources__legend {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-50, 8px) var(--spacing-150, 24px);
  margin: 0;
  padding: 0;
  list-style: none;
  font-size: var(--font-size-small, 0.875rem);
}
.sources__legend li {
  display: flex;
  align-items: center;
  gap: var(--spacing-25, 4px);
}
.sources__swatch {
  width: 12px;
  height: 12px;
  border-radius: 3px;
}
.sources__code {
  margin-left: var(--spacing-25, 4px);
  font-family: var(--font-family-monospace, monospace);
  font-size: 0.75rem;
  color: var(--color-subtle);
}
.sources__rows {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-150, 24px);
}
.sources__row {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-25, 4px);
}
.sources__name {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--spacing-25, 4px) var(--spacing-75, 12px);
}
.sources__meta,
.sources__caption,
.sources__domains {
  font-size: var(--font-size-small, 0.875rem);
  color: var(--color-subtle);
}
.sources__caption {
  color: var(--color-base);
}
.sources__bar {
  display: flex;
  gap: 2px;
  height: 22px;
  margin: var(--spacing-25, 4px) 0;
}
.sources__seg {
  min-width: 3px;
}
.sources__seg:first-child {
  border-radius: 4px 0 0 4px;
}
.sources__seg:last-child {
  border-radius: 0 4px 4px 0;
}
.sources__seg:only-child {
  border-radius: 4px;
}
.sources__none {
  font-size: var(--font-size-small, 0.875rem);
  color: var(--color-subtle);
}
.sources__domain {
  font-family: var(--font-family-monospace, monospace);
}
.isbn--FI { background: var(--isbn-FI); }
.isbn--SE { background: var(--isbn-SE); }
.isbn--DE { background: var(--isbn-DE); }
.isbn--EN { background: var(--isbn-EN); }
.isbn--RU { background: var(--isbn-RU); }
.isbn--EE { background: var(--isbn-EE); }
.isbn--UA { background: var(--isbn-UA); }
.isbn--other { background: var(--isbn-other); }
.sources__table summary {
  cursor: pointer;
  color: var(--color-progressive);
  font-size: var(--font-size-small, 0.875rem);
}
.sources__table table {
  margin-top: var(--spacing-75, 12px);
  border-collapse: collapse;
  font-size: var(--font-size-small, 0.875rem);
  font-variant-numeric: tabular-nums;
}
.sources__table th,
.sources__table td {
  padding: 4px 12px 4px 0;
  border-bottom: 1px solid var(--border-color-subtle);
  text-align: right;
}
.sources__table th:first-child {
  text-align: left;
}
</style>
