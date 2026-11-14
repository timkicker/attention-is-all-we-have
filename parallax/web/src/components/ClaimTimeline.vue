<script setup lang="ts">
// The life of one claim and of its matches in the other editions: what each edition said at the chosen
// date, and bars over the whole history.
import { computed, ref, watch } from 'vue'
import { CdxMessage, CdxProgressBar } from '@wikimedia/codex'
import { api, type Cell, type Life, type Timeline } from '../api'
import { langName, shortDate } from '../langs'
import { addExactDates } from '../snaps'
import ClaimCell from './ClaimCell.vue'
import LifeBars from './LifeBars.vue'

const props = defineProps<{ claimKey: string; asOf: string }>()

const data = ref<Timeline | null>(null)
const error = ref('')
const loading = ref(false)

watch(
  () => props.claimKey,
  async (key) => {
    const [lang, page, h] = key.split(':')
    if (!lang || !page || !h) return
    loading.value = true
    error.value = ''
    try {
      data.value = await api.timeline(lang, Number(page), h)
      addExactDates(data.value.lives)
    } catch (e) {
      error.value = (e as Error).message
      data.value = null
    } finally {
      loading.value = false
    }
  },
  { immediate: true },
)

const ORDER = ['fi', 'sv', 'de', 'en', 'ru', 'et', 'uk']
const instant = computed(() => (props.asOf ? Date.parse(`${props.asOf.slice(0, 10)}T00:00:00Z`) : Date.now()))
const langs = computed(() => {
  if (!data.value) return []
  const own = data.value.claim.lang
  return [own, ...ORDER.filter((l) => l !== own && data.value!.lives.some((x) => x.lang === l))]
})

function aliveAt(lang: string): Life | undefined {
  const t = instant.value
  const alive = (data.value?.lives ?? []).filter(
    (l) => l.lang === lang && Date.parse(l.born!) <= t && (!l.died || Date.parse(l.died) > t),
  )
  return alive.sort((a, b) => Date.parse(b.born!) - Date.parse(a.born!))[0]
}

function cellFor(lang: string): Cell {
  const own = lang === data.value?.claim.lang
  const l = aliveAt(lang)
  if (!l)
    return {
      status: 'not_found', h: null, page_id: null, text: null, gloss: null, dist: null, verdict: null, marks: [],
      born: null, died: null, born_rev: null, died_rev: null, time_precision: null, oldid_url: null,
    }
  return {
    status: own ? 'anchor' : l.verdict ? 'matched' : 'candidate',
    h: l.h,
    page_id: l.page_id,
    text: l.text,
    gloss: null,
    dist: null,
    verdict: l.verdict,
    marks: [],
    born: l.born,
    died: l.died,
    born_rev: l.born_rev,
    died_rev: l.died_rev,
    time_precision: l.time_precision,
    oldid_url: `https://${l.lang}.wikipedia.org/w/index.php?oldid=${l.born_rev}`,
  }
}
</script>

<template>
  <section class="claim-timeline" aria-label="Timeline of one claim" :data-claim="claimKey">
    <CdxProgressBar v-if="loading" inline aria-label="Loading the timeline" />
    <CdxMessage v-if="error" type="error">{{ error }}</CdxMessage>
    <template v-if="data">
      <header class="claim-timeline__head">
        <p class="claim-timeline__kicker">
          {{ langName(data.claim.lang) }} claim<span v-if="data.claim.section"> in “{{ data.claim.section }}”</span>,
          and what each edition said on <b>{{ asOf ? shortDate(asOf) : 'today' }}</b>
        </p>
        <p class="claim-timeline__claim" :lang="data.claim.lang">{{ data.claim.text }}</p>
      </header>
      <div class="claim-timeline__cells">
        <ClaimCell
          v-for="lang in langs"
          :key="lang"
          :lang="lang"
          :cell="cellFor(lang)"
          :anchor-lang="data.claim.lang"
          :data-focus-lang="lang"
        />
      </div>
      <LifeBars :lives="data.lives" :as-of="asOf" :claim-lang="data.claim.lang" />
    </template>
  </section>
</template>

<style scoped>
.claim-timeline {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-100, 16px);
}
.claim-timeline__head p {
  margin: 0;
}
.claim-timeline__kicker {
  color: var(--color-subtle);
  font-size: var(--font-size-small, 0.875rem);
}
.claim-timeline__claim {
  margin-top: var(--spacing-25, 4px) !important;
  font-family: var(--font-family-serif);
  font-size: 1.125rem;
}
.claim-timeline__cells {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: var(--spacing-50, 8px);
}
@media (max-width: 720px) {
  .claim-timeline__cells {
    grid-template-columns: 1fr;
  }
}
</style>
