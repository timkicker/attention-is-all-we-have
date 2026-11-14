<script setup lang="ts">
// Under the hood: the one statement the demo rests on, run live, and the numbers behind the data.
import { computed, onMounted, ref } from 'vue'
import { CdxButton, CdxMessage, CdxProgressBar } from '@wikimedia/codex'
import { api, type Health, type Statement } from '../api'
import { state } from '../state'
import SqlPanel from '../components/SqlPanel.vue'

const canonical = ref<Statement | null>(null)
const others = ref<Statement[]>([])
const asOfUsed = ref('')
const stats = ref<Record<string, unknown>>({})
const health = ref<Health | null>(null)
const loading = ref(false)
const error = ref('')

const isCanonical = (s: Statement) => /FOR SYSTEM_TIME AS OF/.test(s.text) && /VEC_DISTANCE_COSINE/.test(s.text)

async function measure() {
  loading.value = true
  error.value = ''
  try {
    // Today first; a date the alignment cache holds answers from the cache, then an uncached date shows the statement.
    for (const asOf of [state.as_of || undefined, '2016-01-01']) {
      const body = await api.compare({ topic: state.topic, anchor: 'fi', as_of: asOf, limit: 5 })
      const hit = body.sql.find(isCanonical)
      if (hit) {
        canonical.value = hit
        others.value = body.sql.filter((s) => s !== hit)
        asOfUsed.value = body.as_of
        return
      }
    }
    error.value = 'No statement with both FOR SYSTEM_TIME AS OF and VEC_DISTANCE_COSINE in the last response.'
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  measure()
  try {
    stats.value = (await api.stats()).stats as Record<string, unknown>
  } catch {
    stats.value = {}
  }
  try {
    health.value = await api.health()
  } catch {
    health.value = null
  }
})

const n = (x: unknown) => (typeof x === 'number' ? x.toLocaleString('en-US') : String(x))
const scale = computed(() => {
  const s = stats.value
  const c = health.value?.counts as Record<string, number> | undefined
  const judge = s.judge_eval as { accuracy?: number; kappa?: number; n?: number } | undefined
  const rate = s.embed_rate as number | { per_s?: number; gpu?: string } | undefined
  const rows: { label: string; value: string | null; note?: string }[] = [
    { label: 'Revisions read', value: s.revisions_total != null ? n(s.revisions_total) : null },
    {
      label: 'Sentence lives',
      value: s.lives_total != null ? n(s.lives_total) : c ? n((c.claim ?? 0) + (c.claim_life_fi ?? 0)) : null,
      note: s.lives_total == null && c ? 'counted from the loaded tables' : undefined,
    },
    { label: 'Distinct sentences', value: s.distinct_texts != null ? n(s.distinct_texts) : null },
    {
      label: 'Vectors',
      value: s.vectors != null ? n(s.vectors) : c ? n(c.claim ?? 0) : null,
      note: s.vectors == null && c ? 'counted from the loaded tables' : undefined,
    },
    {
      label: 'Embedding rate',
      value: rate == null ? null : typeof rate === 'number' ? `${n(rate)} sentences/s` : `${n(rate.per_s ?? '')} sentences/s`,
      note: typeof rate === 'object' && rate?.gpu ? rate.gpu : undefined,
    },
    {
      label: 'Judge agreement with hand labels',
      value: judge?.accuracy != null ? `${Math.round(judge.accuracy * 100)} %` : null,
      note: judge?.n ? `${judge.n} gold pairs${judge.kappa != null ? `, kappa ${judge.kappa.toFixed(2)}` : ''}` : undefined,
    },
    {
      label: 'Judge calls',
      value: s.judge_calls != null ? n(s.judge_calls) : c ? n(c.verdict ?? 0) : null,
      note: s.judge_calls == null && c ? 'verdicts stored in the database' : undefined,
    },
  ]
  return rows
})
</script>

<template>
  <section class="hood" aria-label="Under the hood">
    <header>
      <h2 class="hood__title">Under the hood</h2>
      <p class="hood__lead">
        Every sentence of every edition is a row of one MariaDB table with system versioning: the period of the row is the
        time Wikipedia stated the sentence. Compare cuts all editions at one instant with
        <code>FOR SYSTEM_TIME AS OF</code> and finds the nearest sentence of every other edition with
        <code>VEC_DISTANCE_COSINE</code> on a vector stored in the same row, in one statement.
      </p>
    </header>

    <div class="hood__canonical">
      <div class="hood__bar">
        <h3 class="hood__h3">The statement behind Compare, run just now</h3>
        <CdxButton :disabled="loading" @click="measure">Run again</CdxButton>
      </div>
      <CdxProgressBar v-if="loading" inline aria-label="Running the statement" />
      <CdxMessage v-if="error" type="warning">{{ error }}</CdxMessage>
      <template v-if="canonical && !loading">
        <p class="hood__timing" data-testid="hood-timing">
          <b>{{ canonical.ms.toFixed(1) }} ms</b>, {{ canonical.rows.toLocaleString('en-US') }} rows, as of
          {{ asOfUsed.slice(0, 10) }}<template v-if="canonical.index === 'emb'">, through the vector index</template>.
        </p>
        <SqlPanel :statements="[canonical]" title="Statement" open />
        <SqlPanel v-if="others.length" :statements="others" title="The other statements of the same request" />
      </template>
    </div>

    <div>
      <h3 class="hood__h3">The data</h3>
      <dl class="hood__stats" data-testid="hood-stats">
        <div v-for="s in scale" :key="s.label" class="hood__stat">
          <dt>{{ s.label }}</dt>
          <dd>
            <span v-if="s.value !== null" class="hood__num">{{ s.value }}</span>
            <span v-else class="hood__pending">not computed yet</span>
            <span v-if="s.note" class="hood__note">{{ s.note }}</span>
          </dd>
        </div>
      </dl>
      <p v-if="health" class="hood__engine">
        Seed <b>{{ health.seed }}</b>, engine <b>{{ health.engine }}</b>, judge model <b>{{ health.model_id }}</b>.
      </p>
    </div>
  </section>
</template>

<style scoped>
.hood {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-200, 32px);
  max-width: 1080px;
}
.hood p,
.hood__title,
.hood__h3 {
  margin: 0;
}
.hood__title {
  font-family: var(--font-family-serif);
  font-size: 1.5rem;
  font-weight: normal;
}
.hood__lead {
  max-width: 75ch;
  margin-top: var(--spacing-50, 8px) !important;
  color: var(--color-subtle);
}
.hood__h3 {
  font-size: 1rem;
}
.hood__bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-75, 12px);
}
.hood__canonical :deep(.sql-panel) {
  margin-top: var(--spacing-75, 12px);
}
.hood__timing {
  margin-top: var(--spacing-75, 12px) !important;
  font-size: 1.125rem;
}
.hood__stats {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: var(--spacing-100, 16px);
  margin: var(--spacing-75, 12px) 0 0;
}
.hood__stat {
  padding: var(--spacing-75, 12px);
  border: var(--border-width-base, 1px) solid var(--border-color-subtle);
  border-radius: var(--border-radius-base, 2px);
}
.hood__stat dt {
  font-size: var(--font-size-small, 0.875rem);
  color: var(--color-subtle);
}
.hood__stat dd {
  display: flex;
  flex-direction: column;
  margin: var(--spacing-25, 4px) 0 0;
}
.hood__num {
  font-family: var(--font-family-serif);
  font-size: 1.5rem;
}
.hood__pending,
.hood__note {
  font-size: var(--font-size-small, 0.875rem);
  color: var(--color-subtle);
}
.hood__engine {
  margin-top: var(--spacing-100, 16px) !important;
  color: var(--color-subtle);
}
</style>
