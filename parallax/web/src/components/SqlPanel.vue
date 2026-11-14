<script setup lang="ts">
// The SQL behind a panel: every statement of its last response with its time, row count and index.
import { computed } from 'vue'
import { CdxInfoChip } from '@wikimedia/codex'
import type { Statement } from '../api'

const props = withDefaults(defineProps<{ statements: Statement[]; source?: string; open?: boolean; title?: string }>(), {
  source: '',
  open: false,
  title: 'SQL behind this view',
})

const KEYWORDS = /(FOR SYSTEM_TIME (?:AS OF(?: TIMESTAMP)?|ALL)|VEC_DISTANCE_COSINE|VEC_FromText|FORCE INDEX|IGNORE INDEX)/g

function pieces(text: string) {
  return text.split(KEYWORDS).map((t, i) => ({ t, key: i % 2 === 1 }))
}

const total = computed(() => props.statements.reduce((a, s) => a + s.ms, 0))
const fmt = (ms: number) => (ms < 10 ? ms.toFixed(1) : Math.round(ms).toString())
</script>

<template>
  <details class="sql-panel" :open="open" data-testid="sql-panel">
    <summary class="sql-panel__summary">
      {{ title }}: {{ statements.length }} statement{{ statements.length === 1 ? '' : 's' }}, {{ fmt(total) }} ms
      <span v-if="source" class="sql-panel__source">{{ source }}</span>
    </summary>
    <ol class="sql-panel__list">
      <li v-for="(s, i) in statements" :key="i" class="sql-panel__item" data-testid="sql-statement">
        <div class="sql-panel__meta">
          <span>{{ fmt(s.ms) }} ms</span>
          <span>{{ s.rows.toLocaleString('en-US') }} row{{ s.rows === 1 ? '' : 's' }}</span>
          <CdxInfoChip v-if="s.index === 'emb'" status="notice">vector index</CdxInfoChip>
        </div>
        <pre class="sql-panel__text"><code><template v-for="(p, j) in pieces(s.text)" :key="j"><b v-if="p.key" class="sql-panel__kw">{{ p.t }}</b><template v-else>{{ p.t }}</template></template></code></pre>
      </li>
    </ol>
  </details>
</template>

<style scoped>
.sql-panel {
  margin-top: var(--spacing-200, 32px);
  border: var(--border-width-base, 1px) solid var(--border-color-subtle);
  border-radius: var(--border-radius-base, 2px);
  background: var(--background-color-neutral-subtle);
}
.sql-panel__summary {
  padding: var(--spacing-50, 8px) var(--spacing-100, 16px);
  cursor: pointer;
  font-size: var(--font-size-small, 0.875rem);
  color: var(--color-subtle);
}
.sql-panel__source {
  margin-left: var(--spacing-75, 12px);
  font-family: var(--font-family-monospace, monospace);
}
.sql-panel__list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-100, 16px);
  margin: 0;
  padding: 0 var(--spacing-100, 16px) var(--spacing-100, 16px) var(--spacing-200, 32px);
}
.sql-panel__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--spacing-75, 12px);
  margin-bottom: var(--spacing-25, 4px);
  font-size: var(--font-size-small, 0.875rem);
  color: var(--color-subtle);
}
.sql-panel__text {
  margin: 0;
  padding: var(--spacing-75, 12px);
  overflow-x: auto;
  border-radius: var(--border-radius-base, 2px);
  background: var(--background-color-base);
  font-family: var(--font-family-monospace, monospace);
  font-size: 0.8125rem;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}
.sql-panel__kw {
  color: var(--color-progressive);
}
</style>
