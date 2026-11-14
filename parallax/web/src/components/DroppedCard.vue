<script setup lang="ts">
// One dropped sentence: what it said, how long, the edit that removed it and the editions that still state it.
import { computed } from 'vue'
import { CdxInfoChip } from '@wikimedia/codex'
import type { DroppedRow } from '../api'
import { langDir, langName, shortDate } from '../langs'
import { VERDICT } from '../verdicts'

const props = defineProps<{ row: DroppedRow }>()

const REASON: Record<string, string> = {
  unsourced: 'edit comment says the text had no source',
  error: 'edit comment mentions a correction',
  speculation: 'edit comment mentions speculation',
}

function span(days: number): string {
  const years = Math.floor(days / 365)
  const months = Math.floor((days % 365) / 30)
  if (!years) return `${months || 1} month${months === 1 ? '' : 's'}`
  return months ? `${years} year${years === 1 ? '' : 's'} ${months} month${months === 1 ? '' : 's'}` : `${years} year${years === 1 ? '' : 's'}`
}

const stated = computed(() => {
  const r = props.row
  const approx = r.time_precision === 'snapshot' ? ', dates known to the year' : ''
  return `stated for ${span(r.days)}, ${shortDate(r.born)} to ${shortDate(r.died)}${approx}`
})
</script>

<template>
  <article class="dropped-card" :data-lang="row.lang" :data-h="row.h">
    <header class="dropped-card__head">
      <span class="dropped-card__lang">{{ row.lang }}</span>
      <span class="dropped-card__title" :lang="row.lang">{{ row.title }}</span>
      <span class="dropped-card__span">{{ stated }}</span>
    </header>

    <p class="dropped-card__text" :lang="row.lang" :dir="langDir(row.lang)">{{ row.text }}</p>
    <p v-if="row.gloss && row.lang !== 'en'" class="dropped-card__gloss" lang="en">
      <span class="dropped-card__gloss-label">machine translation</span> {{ row.gloss }}
    </p>

    <p class="dropped-card__removed">
      <span>
        {{ langName(row.lang) }} stopped saying it on <b>{{ shortDate(row.died) }}</b>
        <template v-if="row.died_comment">
          with the edit comment <q :lang="row.lang">{{ row.died_comment }}</q>
        </template>
        <template v-if="REASON[row.reason]"> ({{ REASON[row.reason] }})</template>.
      </span>
      <a v-if="row.last_url" :href="row.last_url" target="_blank" rel="noopener">Open the last revision that had it</a>
    </p>

    <section v-if="row.alive_in.length" class="dropped-card__alive" aria-label="Editions that still state it">
      <h3 class="dropped-card__alive-title">Still stated in {{ row.alive_in.length }} edition{{ row.alive_in.length === 1 ? '' : 's' }}</h3>
      <ul class="dropped-card__chips">
        <li v-for="a in row.alive_in" :key="a.lang">
          <CdxInfoChip :status="a.verdict ? VERDICT[a.verdict.label].status : 'subtle'">
            {{ a.lang }}: {{ a.verdict ? VERDICT[a.verdict.label].label : 'nearest, not judged' }}
          </CdxInfoChip>
        </li>
      </ul>
      <details class="dropped-card__details">
        <summary>Show their sentences</summary>
        <ul class="dropped-card__quotes">
          <li v-for="a in row.alive_in" :key="a.lang" :data-alive-lang="a.lang">
            <span class="dropped-card__lang">{{ a.lang }}</span>
            <span :lang="a.lang" :dir="langDir(a.lang)">{{ a.text }}</span>
            <a v-if="a.oldid_url" :href="a.oldid_url" target="_blank" rel="noopener">Open on {{ a.lang }}.wikipedia</a>
          </li>
        </ul>
      </details>
    </section>
  </article>
</template>

<style scoped>
.dropped-card {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-50, 8px);
  padding: var(--spacing-100, 16px);
  border: var(--border-width-base, 1px) solid var(--border-color-subtle);
  border-left: 4px solid var(--border-color-base);
  border-radius: var(--border-radius-base, 2px);
  background: var(--background-color-base);
}
.dropped-card p {
  margin: 0;
}
.dropped-card__head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--spacing-25, 4px) var(--spacing-75, 12px);
}
.dropped-card__lang {
  font-family: var(--font-family-monospace, monospace);
  font-size: 0.75rem;
  font-weight: bold;
  text-transform: uppercase;
  color: var(--color-subtle);
}
.dropped-card__title {
  font-family: var(--font-family-serif);
  color: var(--color-subtle);
}
.dropped-card__span {
  margin-left: auto;
  font-size: var(--font-size-small, 0.875rem);
  color: var(--color-subtle);
}
.dropped-card__text {
  font-family: var(--font-family-serif);
  font-size: 1.0625rem;
  line-height: 1.5;
}
.dropped-card__gloss {
  font-size: var(--font-size-small, 0.875rem);
  color: var(--color-subtle);
}
.dropped-card__gloss-label {
  font-size: 0.6875rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.dropped-card__removed {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-25, 4px) var(--spacing-100, 16px);
  font-size: var(--font-size-small, 0.875rem);
}
.dropped-card__alive {
  padding-top: var(--spacing-50, 8px);
  border-top: var(--border-width-base, 1px) solid var(--border-color-subtle);
}
.dropped-card__alive-title {
  margin: 0 0 var(--spacing-50, 8px);
  font-size: var(--font-size-small, 0.875rem);
  font-weight: bold;
}
.dropped-card__chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-50, 8px);
  margin: 0;
  padding: 0;
  list-style: none;
}
.dropped-card__details {
  margin-top: var(--spacing-50, 8px);
  font-size: var(--font-size-small, 0.875rem);
}
.dropped-card__details summary {
  cursor: pointer;
  color: var(--color-progressive);
}
.dropped-card__quotes {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-50, 8px);
  margin: var(--spacing-50, 8px) 0 0;
  padding: 0;
  list-style: none;
}
.dropped-card__quotes li {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-25, 4px) var(--spacing-75, 12px);
  font-family: var(--font-family-serif);
}
.dropped-card__quotes a {
  font-family: var(--font-family-system-sans);
}
</style>
