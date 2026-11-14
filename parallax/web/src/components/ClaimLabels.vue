<script setup lang="ts">
// One claim of a checked answer: one chip per edition, the evidence behind each chip on demand.
import { computed } from 'vue'
import { CdxInfoChip } from '@wikimedia/codex'
import type { CheckClaim } from '../api'
import { langDir, langName, shortDate } from '../langs'
import type { ChipStatus } from '../verdicts'
import { VERDICT } from '../verdicts'

const props = defineProps<{ claim: CheckClaim }>()

const LABEL: Record<string, ChipStatus> = {
  says: 'success',
  stopped_saying: 'notice',
  contradicts: 'warning',
  not_found: 'subtle',
}

function chipText(lang: string): string {
  const v = props.claim.per_lang[lang]
  if (v.label === 'says') return `${lang}: says`
  if (v.label === 'stopped_saying') {
    const died = v.evidence[0]?.died
    return `${lang}: stopped saying${died ? ` (${died.slice(0, 4)})` : ''}`
  }
  if (v.label === 'contradicts') return `${lang}: differs`
  return `not found in ${lang}`
}

const langs = computed(() => Object.keys(props.claim.per_lang))
const withEvidence = computed(() => langs.value.filter((l) => props.claim.per_lang[l].evidence.length))
</script>

<template>
  <article class="claim-labels" :data-idx="claim.idx">
    <p class="claim-labels__text" lang="en">{{ claim.text }}</p>
    <ul class="claim-labels__chips" aria-label="What each edition says">
      <li v-for="lang in langs" :key="lang" :data-lang="lang" :data-label="claim.per_lang[lang].label">
        <CdxInfoChip :status="LABEL[claim.per_lang[lang].label]">{{ chipText(lang) }}</CdxInfoChip>
      </li>
    </ul>
    <details v-if="withEvidence.length" class="claim-labels__details">
      <summary>Show the sentences behind these labels</summary>
      <ul class="claim-labels__evidence">
        <template v-for="lang in withEvidence" :key="lang">
          <li v-for="e in claim.per_lang[lang].evidence" :key="`${lang}:${e.h}`" :data-evidence-lang="lang">
            <div class="claim-labels__ev-head">
              <span class="claim-labels__lang">{{ lang }}</span>
              <CdxInfoChip v-if="e.verdict" :status="VERDICT[e.verdict.label].status">{{ VERDICT[e.verdict.label].label }}</CdxInfoChip>
              <span class="claim-labels__dates">
                {{ langName(lang) }}, stated {{ shortDate(e.born) }} to {{ e.died ? shortDate(e.died) : 'today' }}
              </span>
            </div>
            <p class="claim-labels__quote" :lang="lang" :dir="langDir(lang)">{{ e.text }}</p>
            <p v-if="e.died_comment" class="claim-labels__comment">
              Edit comment when it was removed: <q :lang="lang">{{ e.died_comment }}</q>
            </p>
            <a v-if="e.oldid_url" :href="e.oldid_url" target="_blank" rel="noopener">Open on {{ lang }}.wikipedia</a>
          </li>
        </template>
      </ul>
    </details>
  </article>
</template>

<style scoped>
.claim-labels {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-50, 8px);
  padding: var(--spacing-100, 16px) 0;
  border-bottom: var(--border-width-base, 1px) solid var(--border-color-subtle);
}
.claim-labels p {
  margin: 0;
}
.claim-labels__text {
  font-family: var(--font-family-serif);
  font-size: 1.0625rem;
}
.claim-labels__chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-50, 8px);
  margin: 0;
  padding: 0;
  list-style: none;
}
.claim-labels__details {
  font-size: var(--font-size-small, 0.875rem);
}
.claim-labels__details summary {
  cursor: pointer;
  color: var(--color-progressive);
}
.claim-labels__evidence {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-75, 12px);
  margin: var(--spacing-75, 12px) 0 0;
  padding: 0;
  list-style: none;
}
.claim-labels__evidence li {
  padding-left: var(--spacing-75, 12px);
  border-left: 2px solid var(--border-color-subtle);
}
.claim-labels__ev-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--spacing-25, 4px) var(--spacing-75, 12px);
}
.claim-labels__lang {
  font-family: var(--font-family-monospace, monospace);
  font-size: 0.75rem;
  font-weight: bold;
  text-transform: uppercase;
  color: var(--color-subtle);
}
.claim-labels__dates,
.claim-labels__comment {
  color: var(--color-subtle);
}
.claim-labels__quote {
  margin: var(--spacing-25, 4px) 0 !important;
  font-family: var(--font-family-serif);
  font-size: 1rem;
}
</style>
