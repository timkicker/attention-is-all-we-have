<script setup lang="ts">
// One line per edition, one bar per sentence life from the revision that added it to the one that removed it.
// Ends known only to a yearly snapshot are hatched over the year before the bound ("known to the year").
import { computed } from 'vue'
import type { Life } from '../api'
import { langName, shortDate } from '../langs'
import { axisFraction, FIRST_YEAR } from '../timeaxis'

const props = defineProps<{ lives: Life[]; asOf: string; claimLang: string }>()

const YEAR = 365 * 24 * 3600 * 1000
const ORDER = ['fi', 'sv', 'de', 'en', 'ru', 'et', 'uk']

function bar(l: Life) {
  const left = axisFraction(l.born) * 100
  const right = axisFraction(l.died) * 100
  const hatch = (iso: string | null) => {
    if (!iso || l.time_precision !== 'snapshot') return null
    const end = axisFraction(iso) * 100
    const start = axisFraction(new Date(Date.parse(iso) - YEAR).toISOString()) * 100
    return { left: Math.max(left, start) - left, width: end - Math.max(left, start) }
  }
  const lines = [
    l.text,
    `added ${shortDate(l.born)} (revision ${l.born_rev})`,
    l.died ? `removed ${shortDate(l.died)} (revision ${l.died_rev})${l.died_comment ? `: "${l.died_comment}"` : ''}` : 'still stated',
    l.time_precision === 'snapshot' ? 'dates known to the year (yearly snapshots)' : 'exact revision dates',
  ]
  return {
    life: l,
    left,
    width: Math.max(right - left, 0.6),
    startHatch: hatch(l.born),
    endHatch: l.died ? hatch(l.died) : null,
    title: lines.join('\n'),
    href: `https://${l.lang}.wikipedia.org/w/index.php?oldid=${l.born_rev}`,
  }
}

const rows = computed(() => {
  const langs = [...new Set(props.lives.map((l) => l.lang))].sort((a, b) => {
    if (a === props.claimLang) return -1
    if (b === props.claimLang) return 1
    return ORDER.indexOf(a) - ORDER.indexOf(b)
  })
  return langs.map((lang) => ({ lang, bars: props.lives.filter((l) => l.lang === lang).map(bar) }))
})
const cursor = computed(() => axisFraction(props.asOf ? `${props.asOf.slice(0, 10)}T00:00:00Z` : null) * 100)
const years = computed(() => {
  const out = []
  for (let y = FIRST_YEAR + 2; y <= new Date().getUTCFullYear(); y += 5) out.push({ y, left: axisFraction(`${y}-01-01T00:00:00Z`) * 100 })
  return out
})
const anySnapshot = computed(() => props.lives.some((l) => l.time_precision === 'snapshot'))
</script>

<template>
  <figure class="life-bars" aria-label="Life of the sentence in every edition">
    <div v-for="r in rows" :key="r.lang" class="life-bars__row" :data-lang="r.lang">
      <span class="life-bars__lang" :title="langName(r.lang)">{{ r.lang }}</span>
      <div class="life-bars__lane">
        <span v-for="y in years" :key="y.y" class="life-bars__grid" :style="{ left: `${y.left}%` }" />
        <a
          v-for="(b, i) in r.bars"
          :key="i"
          class="life-bars__bar"
          :class="{
            'life-bars__bar--judged': b.life.verdict && b.life.verdict.label !== 'different',
            'life-bars__bar--own': r.lang === claimLang,
          }"
          :style="{ left: `${b.left}%`, width: `${b.width}%` }"
          :href="b.href"
          target="_blank"
          rel="noopener"
          :title="b.title"
          :aria-label="b.title"
        >
          <span
            v-if="b.startHatch"
            class="life-bars__hatch"
            :style="{ left: '0', width: `${(b.startHatch.width / b.width) * 100}%` }"
          />
          <span
            v-if="b.endHatch"
            class="life-bars__hatch"
            :style="{ right: '0', width: `${(b.endHatch.width / b.width) * 100}%` }"
          />
        </a>
        <span class="life-bars__cursor" :style="{ left: `${cursor}%` }" />
      </div>
    </div>
    <div class="life-bars__axis" aria-hidden="true">
      <span class="life-bars__lang" />
      <div class="life-bars__lane life-bars__lane--axis">
        <span v-for="y in years" :key="y.y" class="life-bars__year" :style="{ left: `${y.left}%` }">{{ y.y }}</span>
      </div>
    </div>
    <figcaption class="life-bars__legend">
      Each bar is one wording of the sentence, from the revision that added it to the one that removed it. Blue bars are
      matches the judge confirmed. The line marks the chosen date.
      <template v-if="anySnapshot"> Hatched ends are known to the year: the data has one snapshot per year there.</template>
    </figcaption>
  </figure>
</template>

<style scoped>
.life-bars {
  margin: 0;
}
.life-bars__row,
.life-bars__axis {
  display: flex;
  align-items: center;
  gap: var(--spacing-50, 8px);
}
.life-bars__row {
  height: 22px;
}
.life-bars__lang {
  flex: none;
  width: 2.5em;
  font-family: var(--font-family-monospace, monospace);
  font-size: 0.75rem;
  font-weight: bold;
  text-transform: uppercase;
  color: var(--color-subtle);
}
.life-bars__lane {
  position: relative;
  flex: 1;
  height: 100%;
  border-bottom: var(--border-width-base, 1px) solid var(--border-color-muted, var(--border-color-subtle));
}
.life-bars__lane--axis {
  height: 18px;
  border: 0;
}
.life-bars__grid {
  position: absolute;
  top: 0;
  bottom: 0;
  border-left: 1px dotted var(--border-color-subtle);
}
.life-bars__year {
  position: absolute;
  transform: translateX(-50%);
  font-size: 0.6875rem;
  color: var(--color-subtle);
}
.life-bars__bar {
  position: absolute;
  top: 5px;
  height: 12px;
  overflow: hidden;
  border-radius: 2px;
  background: var(--border-color-base);
  opacity: 0.75;
}
.life-bars__bar--judged {
  background: var(--color-progressive);
  opacity: 1;
}
.life-bars__bar--own {
  background: var(--color-emphasized);
  opacity: 1;
}
.life-bars__bar:hover,
.life-bars__bar:focus-visible {
  outline: 2px solid var(--color-progressive);
  outline-offset: 1px;
}
.life-bars__hatch {
  position: absolute;
  top: 0;
  bottom: 0;
  background: repeating-linear-gradient(
    135deg,
    var(--background-color-base) 0 2px,
    transparent 2px 5px
  );
}
.life-bars__cursor {
  position: absolute;
  top: -2px;
  bottom: -2px;
  border-left: 2px solid var(--color-warning);
  pointer-events: none;
}
.life-bars__legend {
  margin-top: var(--spacing-50, 8px);
  font-size: 0.75rem;
  color: var(--color-subtle);
}
</style>
