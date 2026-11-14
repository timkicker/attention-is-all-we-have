<script setup lang="ts">
// Compare: one row per claim of the anchor edition, one column per edition, all cut at the same instant.
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { CdxButton, CdxField, CdxMessage, CdxProgressBar, CdxSelect } from '@wikimedia/codex'
import { api, type Cell, type Compare, type CompareRow, type Topic } from '../api'
import { langName, shortDate } from '../langs'
import { navigate, state } from '../state'
import EmptyState from '../components/EmptyState.vue'
import ClaimCell from '../components/ClaimCell.vue'

const props = defineProps<{ topics: Topic[]; debounceMs?: number }>()
const emit = defineEmits<{ open: [lang: string, cell: Cell, row: CompareRow] }>()

const PAGE = 25
const data = ref<Compare | null>(null)
const rows = ref<CompareRow[]>([])
const loading = ref(false)
const error = ref('')
let controller: AbortController | null = null
let timer: ReturnType<typeof setTimeout> | undefined

const topic = computed(() => props.topics.find((t) => t.topic_id === state.topic))
const titles = computed(() => Object.fromEntries((topic.value?.editions ?? []).map((e) => [e.lang, e.title])))
const anchorItems = computed(() =>
  (topic.value?.editions ?? [{ lang: state.anchor }]).map((e) => ({ value: e.lang, label: `${langName(e.lang)} (${e.lang})` })),
)
const anchor = computed({ get: () => state.anchor, set: (v: string) => navigate({ anchor: v }) })

async function load(offset = 0) {
  controller?.abort()
  const mine = (controller = new AbortController())
  loading.value = true
  error.value = ''
  try {
    const body = await api.compare(
      {
        topic: state.topic,
        anchor: state.anchor,
        as_of: state.as_of || undefined,
        section: state.section || undefined,
        offset,
        limit: PAGE,
      },
      { signal: mine.signal },
    )
    data.value = body
    rows.value = offset ? [...rows.value, ...body.rows] : body.rows
  } catch (e) {
    if (mine.signal.aborted) return
    error.value = (e as Error).message
  } finally {
    if (controller === mine) loading.value = false
  }
}

watch(
  () => [state.topic, state.anchor, state.as_of, state.section],
  () => {
    clearTimeout(timer)
    if (props.debounceMs) timer = setTimeout(() => load(0), props.debounceMs)
    else load(0)
  },
  { immediate: true },
)
onBeforeUnmount(() => {
  clearTimeout(timer)
  controller?.abort()
})

const langs = computed(() => data.value?.langs ?? [])
const gridStyle = computed(() => ({ '--cols': String(langs.value.length || 1) }))
const sections = computed(() => {
  const out: { section: string; rows: CompareRow[] }[] = []
  for (const r of rows.value) {
    const last = out.at(-1)
    if (last && last.section === r.section) last.rows.push(r)
    else out.push({ section: r.section, rows: [r] })
  }
  return out
})
const sectionLabel = (s: string) => (s === '[lead]' ? 'Introduction' : s === '[infobox]' ? 'Infobox' : s)
const more = computed(() => (data.value ? data.value.total_rows - rows.value.length : 0))
</script>

<template>
  <section class="compare" aria-label="Compare editions">
    <div class="compare__toolbar">
      <CdxField class="compare__anchor">
        <template #label>Anchor edition</template>
        <CdxSelect v-model:selected="anchor" :menu-items="anchorItems" />
      </CdxField>
      <p v-if="data" class="compare__summary">
        {{ data.total_rows }} claims in the {{ langName(data.anchor) }} edition on
        <b>{{ shortDate(data.as_of) }}</b>, each lined up with the nearest sentence of every other edition.
        <template v-if="state.section">
          Only the section <b>{{ sectionLabel(state.section) }}</b>.
          <a href="#" @click.prevent="navigate({ section: '' })">Show every section</a>
        </template>
      </p>
    </div>

    <CdxProgressBar v-if="loading" inline aria-label="Loading claims" class="compare__progress" />
    <CdxMessage v-if="error" type="error">{{ error }}</CdxMessage>

    <EmptyState
      v-else-if="data && !rows.length && !loading"
      :title="`No ${langName(data.anchor)} claims on this date`"
      detail="The anchor edition has no parsed revision before this date. Move the date later or pick another anchor."
    />

    <div v-if="rows.length" class="compare__grid" :style="gridStyle" role="table" aria-label="Claims per edition">
      <div class="compare__head" role="row">
        <div v-for="lang in langs" :key="lang" class="compare__edition" role="columnheader" :lang="lang">
          <span class="compare__edition-name">{{ langName(lang) }}</span>
          <span class="compare__edition-title">{{ titles[lang] }}</span>
          <a
            v-if="data?.editions[lang]"
            class="compare__edition-rev"
            :href="`https://${lang}.wikipedia.org/w/index.php?oldid=${data.editions[lang].rev_id}`"
            target="_blank"
            rel="noopener"
          >revision of {{ shortDate(data.editions[lang].rev_ts) }}</a>
          <span v-else class="compare__edition-rev">no revision yet</span>
        </div>
      </div>
      <template v-for="s in sections" :key="s.section">
        <h3 class="compare__section" role="row">
          <span role="cell">{{ sectionLabel(s.section) }}</span>
        </h3>
        <div v-for="r in s.rows" :key="r.row_id" class="compare__row" role="row" :data-row="r.row_id">
          <div v-for="lang in langs" :key="lang" role="cell" class="compare__cell">
            <ClaimCell :lang="lang" :cell="r.cells[lang]" :anchor-lang="data!.anchor" @open="emit('open', lang, r.cells[lang], r)" />
          </div>
        </div>
      </template>
    </div>

    <div v-if="more > 0" class="compare__more">
      <CdxButton :disabled="loading" @click="load(rows.length)">Show {{ Math.min(more, PAGE) }} more of {{ more }}</CdxButton>
    </div>
  </section>
</template>

<style scoped>
.compare__toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: var(--spacing-100, 16px) var(--spacing-150, 24px);
  margin-bottom: var(--spacing-100, 16px);
}
.compare__anchor {
  margin: 0;
}
.compare__summary {
  margin: 0;
  max-width: 70ch;
  color: var(--color-subtle);
}
.compare__progress {
  margin-bottom: var(--spacing-100, 16px);
}
.compare__grid {
  display: grid;
  grid-template-columns: repeat(var(--cols), minmax(150px, 1fr));
  gap: var(--spacing-50, 8px);
}
.compare__head,
.compare__row {
  display: contents;
}
.compare__edition {
  position: sticky;
  top: 0;
  z-index: 1;
  display: flex;
  flex-direction: column;
  padding: var(--spacing-50, 8px) var(--spacing-25, 4px);
  border-bottom: 2px solid var(--border-color-base);
  background: var(--background-color-base);
}
.compare__edition-name {
  font-weight: bold;
}
.compare__edition-title {
  font-family: var(--font-family-serif);
  color: var(--color-subtle);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.compare__edition-rev {
  font-size: 0.75rem;
  color: var(--color-subtle);
}
.compare__section {
  grid-column: 1 / -1;
  margin: var(--spacing-100, 16px) 0 0;
  font-family: var(--font-family-serif);
  font-size: 1.125rem;
  font-weight: normal;
  color: var(--color-emphasized);
}
.compare__more {
  margin-top: var(--spacing-150, 24px);
  text-align: center;
}
@media (max-width: 720px) {
  .compare__grid {
    grid-template-columns: 1fr;
  }
  .compare__head {
    display: none;
  }
  .compare__row {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-50, 8px);
    padding-bottom: var(--spacing-100, 16px);
    border-bottom: var(--border-width-base, 1px) solid var(--border-color-subtle);
  }
}
</style>
