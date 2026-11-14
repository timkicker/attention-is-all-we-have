<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { CdxButton, CdxField, CdxMessage, CdxSelect, CdxTab, CdxTabs, CdxTextInput } from '@wikimedia/codex'
import { api, type Topic } from './api'
import { navigate, state, VIEWS, type ViewName } from './state'
import Footer from './components/Footer.vue'
import Wordmark from './components/Wordmark.vue'
import PendingView from './views/PendingView.vue'
import CompareView from './views/CompareView.vue'

const PENDING: Record<ViewName, string> = {
  compare: 'One row per claim of the anchor edition, one column per edition, cut at the chosen date.',
  time: 'Lives of each claim per edition, from the revision that added it to the one that removed it.',
  dropped: 'Claims one edition removed while other editions still state them.',
  check: 'Paste an answer, see per edition whether Wikipedia says it, stopped saying it or does not state it.',
  sources: 'What each edition cites, counted by ISBN group and web domain.',
  ask: 'Quotes from every edition for a question, without generated prose.',
  atlas: 'Topics covered in Finnish, Swedish and English and how far apart the editions are.',
  hood: 'The SQL behind every panel with its time and row count.',
}

const topics = ref<Topic[]>([])
const loadError = ref('')

onMounted(async () => {
  try {
    topics.value = (await api.topics()).topics.filter((t) => t.depth === 'deep')
  } catch (e) {
    loadError.value = (e as Error).message
  }
})

const topicItems = computed(() =>
  topics.value.length
    ? topics.value.map((t) => ({ value: t.topic_id, label: t.label_en, description: `${t.editions.length} editions` }))
    : [{ value: state.topic, label: state.topic }],
)
const topic = computed({ get: () => state.topic, set: (v: string) => navigate({ topic: v }) })
const active = computed({ get: () => state.view, set: (v: string) => navigate({ view: v as ViewName }) })
const asOf = computed({
  get: () => state.as_of,
  set: (v: string) => navigate({ as_of: v }),
})
const today = new Date().toISOString().slice(0, 10)
</script>

<template>
  <div class="shell">
    <header class="topbar">
      <div class="topbar__brand">
        <Wordmark />
        <span class="topbar__tagline">Seven editions, one instant</span>
      </div>
      <div class="topbar__controls">
        <CdxField class="topbar__field">
          <template #label>Topic</template>
          <CdxSelect v-model:selected="topic" :menu-items="topicItems" default-label="Choose a topic" />
        </CdxField>
        <CdxField class="topbar__field">
          <template #label>As of</template>
          <div class="topbar__date">
            <CdxTextInput v-model="asOf" input-type="date" :max="today" min="2001-01-15" aria-label="As of date" />
            <CdxButton weight="quiet" :disabled="!asOf" @click="asOf = ''">Today</CdxButton>
          </div>
        </CdxField>
      </div>
    </header>

    <CdxMessage v-if="loadError" type="error" class="shell__notice">
      {{ loadError }} Start the API with <code>make api</code>.
    </CdxMessage>

    <main class="shell__main">
      <CdxTabs v-model:active="active" :framed="false">
        <CdxTab v-for="v in VIEWS" :key="v.name" :name="v.name" :label="v.label">
          <div v-if="state.view === v.name" class="view">
            <CompareView v-if="v.name === 'compare'" :topics="topics" />
            <PendingView v-else :label="v.label" :detail="PENDING[v.name]" />
          </div>
        </CdxTab>
      </CdxTabs>
    </main>

    <Footer />
  </div>
</template>

<style scoped>
.shell {
  max-width: 1600px;
  margin: 0 auto;
  padding: 0 var(--spacing-150, 24px);
}
.topbar {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--spacing-100, 16px) var(--spacing-200, 32px);
  padding: var(--spacing-100, 16px) 0 var(--spacing-75, 12px);
}
.topbar__brand {
  display: flex;
  align-items: baseline;
  gap: var(--spacing-75, 12px);
}
.topbar__tagline {
  color: var(--color-subtle);
  font-size: var(--font-size-small, 0.875rem);
}
.topbar__controls {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-100, 16px);
  align-items: flex-end;
}
.topbar__field {
  margin: 0;
}
.topbar__date {
  display: flex;
  gap: var(--spacing-25, 4px);
}
.shell__notice {
  margin-bottom: var(--spacing-100, 16px);
}
.view {
  padding-top: var(--spacing-150, 24px);
}
@media (max-width: 640px) {
  .shell {
    padding: 0 var(--spacing-100, 16px);
  }
  .topbar__tagline {
    display: none;
  }
  .topbar__controls,
  .topbar__field,
  .topbar__field :deep(.cdx-select-vue) {
    width: 100%;
  }
  .topbar__date {
    width: 100%;
  }
  .topbar__date > :first-child {
    flex: 1;
  }
}
</style>
