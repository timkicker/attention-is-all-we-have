<script setup lang="ts">
// One edition's cell in a Compare row: the original sentence, its gloss, the verdict and what differs.
import { computed } from 'vue'
import { CdxInfoChip } from '@wikimedia/codex'
import type { Cell } from '../api'
import { highlight } from '../highlight'
import { langDir, langName } from '../langs'
import { VERDICT } from '../verdicts'

const props = defineProps<{ lang: string; cell: Cell; anchorLang: string }>()
const emit = defineEmits<{ open: [] }>()

const chip = computed(() => {
  const c = props.cell
  if (c.status === 'anchor') return { label: 'anchor', status: 'subtle' as const }
  if (c.status === 'candidate') return { label: 'nearest, not judged', status: 'subtle' as const }
  if (c.verdict) return VERDICT[c.verdict.label]
  return null
})

const pieces = computed(() =>
  highlight(
    props.cell.text ?? '',
    props.cell.marks.map((m) => ({ text: m.other, kind: m.kind })),
  ),
)
const numberMarks = computed(() => props.cell.marks.filter((m) => m.kind === 'number'))
const termMarks = computed(() => props.cell.marks.filter((m) => m.kind === 'term'))
const clickable = computed(() => props.cell.status !== 'not_found')
</script>

<template>
  <div
    class="claim-cell"
    :class="[`claim-cell--${cell.status}`, { 'claim-cell--clickable': clickable }]"
    :data-lang="lang"
    :data-status="cell.status"
    :tabindex="clickable ? 0 : undefined"
    :role="clickable ? 'button' : undefined"
    :aria-label="clickable ? `${langName(lang)}: show the life of this sentence` : undefined"
    @click="clickable && emit('open')"
    @keydown.enter.prevent="clickable && emit('open')"
    @keydown.space.prevent="clickable && emit('open')"
  >
    <div class="claim-cell__head">
      <span class="claim-cell__lang">{{ lang }}</span>
      <CdxInfoChip v-if="chip" :status="chip.status" class="claim-cell__chip">{{ chip.label }}</CdxInfoChip>
    </div>

    <p v-if="cell.status === 'not_found'" class="claim-cell__missing">not found in {{ lang }}</p>
    <template v-else>
      <p class="claim-cell__text" :lang="lang" :dir="langDir(lang)">
        <template v-for="(p, i) in pieces" :key="i">
          <mark v-if="p.kind" :class="`claim-cell__mark claim-cell__mark--${p.kind}`">{{ p.text }}</mark>
          <template v-else>{{ p.text }}</template>
        </template>
      </p>
      <p v-if="cell.gloss && lang !== 'en'" class="claim-cell__gloss" lang="en">
        <span class="claim-cell__gloss-label">machine translation</span>
        {{ cell.gloss }}
      </p>
      <ul v-if="cell.marks.length" class="claim-cell__marks">
        <li v-for="(m, i) in numberMarks" :key="`n${i}`">
          number differs: <b>{{ m.this }}</b> in {{ anchorLang }}, <b>{{ m.other }}</b> here
        </li>
        <li v-for="(m, i) in termMarks" :key="`t${i}`">
          uses the term <b :lang="lang">{{ m.other }}</b> where {{ anchorLang }} has <b :lang="anchorLang">{{ m.this }}</b>
        </li>
      </ul>
      <div class="claim-cell__foot">
        <a
          v-if="cell.oldid_url"
          class="claim-cell__src"
          :href="cell.oldid_url"
          target="_blank"
          rel="noopener"
          @click.stop
        >Open on {{ lang }}.wikipedia</a>
        <span v-if="cell.dist !== null" class="claim-cell__dist" title="cosine distance between the two sentence vectors">
          distance {{ cell.dist.toFixed(2) }}
        </span>
      </div>
    </template>
  </div>
</template>

<style scoped>
.claim-cell {
  height: 100%;
  padding: var(--spacing-75, 12px);
  border: var(--border-width-base, 1px) solid var(--border-color-subtle);
  border-radius: var(--border-radius-base, 2px);
  background: var(--background-color-base);
  font-size: var(--font-size-small, 0.875rem);
  line-height: var(--line-height-small, 1.5);
}
.claim-cell--anchor {
  border-color: var(--border-color-progressive, var(--color-progressive));
  background: var(--background-color-progressive-subtle);
}
.claim-cell--not_found {
  border-style: dashed;
  background: transparent;
}
.claim-cell--clickable {
  cursor: pointer;
}
.claim-cell--clickable:hover {
  border-color: var(--border-color-interactive, var(--border-color-base));
}
.claim-cell--clickable:focus-visible {
  outline: 2px solid var(--color-progressive);
  outline-offset: 1px;
}
.claim-cell__head {
  display: flex;
  align-items: center;
  gap: var(--spacing-50, 8px);
  margin-bottom: var(--spacing-50, 8px);
  min-height: 24px;
}
.claim-cell__lang {
  font-family: var(--font-family-monospace, monospace);
  font-weight: bold;
  color: var(--color-subtle);
  text-transform: uppercase;
}
.claim-cell__foot {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: 0 var(--spacing-50, 8px);
  margin-top: var(--spacing-50, 8px);
}
.claim-cell__dist {
  color: var(--color-placeholder);
  font-family: var(--font-family-monospace, monospace);
  font-size: 0.75rem;
}
.claim-cell__text {
  margin: 0;
  font-family: var(--font-family-serif);
  font-size: 0.9375rem;
  line-height: 1.45;
  color: var(--color-base);
  overflow-wrap: anywhere;
}
.claim-cell__mark {
  padding: 0 2px;
  border-radius: 2px;
  color: inherit;
}
.claim-cell__mark--number {
  background: var(--background-color-warning-subtle);
  box-shadow: inset 0 -2px 0 var(--color-warning);
}
.claim-cell__mark--term {
  background: var(--background-color-notice-subtle, var(--background-color-neutral-subtle));
  box-shadow: inset 0 -2px 0 var(--color-subtle);
}
.claim-cell__gloss {
  margin: var(--spacing-50, 8px) 0 0;
  color: var(--color-subtle);
}
.claim-cell__gloss-label {
  display: block;
  font-size: 0.75rem;
  color: var(--color-placeholder);
}
.claim-cell__missing {
  margin: 0;
  color: var(--color-subtle);
  font-style: italic;
}
.claim-cell__marks {
  margin: var(--spacing-50, 8px) 0 0;
  padding: 0;
  list-style: none;
  color: var(--color-base);
}
.claim-cell__src {
  font-size: 0.8125rem;
}
</style>
