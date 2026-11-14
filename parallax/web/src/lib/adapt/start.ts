// Start page, search and ingest: raw API -> view model. Owner: P1.
import type { api as Api } from '../api/client'
import type { CellRaw, CompareRes, IngestRes, SearchResultRaw, TopicsRes } from '../api/types'
import { exampleTitle } from '../copy/start'
import {
  LANGS,
  type ExampleLine,
  type IngestEdition,
  type IngestVM,
  type Lang,
  type MarkedText,
  type Result,
  type SearchResult,
  type SearchVM,
  type StartVM,
  type TopicRef,
} from '../model'
import { paths } from '../router.svelte'
import { forgetTopics } from './shared'

type Client = typeof Api

/** The example statement, a known seed v4 id: Finnish says the Soviet Union staged the Mainila shots.
 *  Found by hand in /api/compare; there is no cheap way to pick the best example from data. */
export const EXAMPLE_QID = 'Q134949'
export const EXAMPLE_STATEMENT = { lang: 'fi', pageId: 1256, h: 'abe24bc5f22fda02' }

/** "Faster" offers the last five years; the API gives no estimate for it, so it is a fixed guess. */
const FASTER_YEARS = 5
const FASTER_ETA_S = 60
/** With this little left, offering a faster load makes no sense. */
const FASTER_HIDE_S = 120

/** PreparedTopic plus the edition count, shown when no year span is known. Remove once model.ts carries it. */
export type PreparedWithCount = StartVM['prepared'][number] & { editions: number }

export function toPrepared(raw: TopicsRes): PreparedWithCount[] {
  // The topics list carries no year span, so years stay empty in live mode.
  // The example's article comes first, the rest keep the API's order.
  return [...raw.topics]
    .sort((a, b) => Number(b.wikidata_id === EXAMPLE_QID) - Number(a.wikidata_id === EXAMPLE_QID))
    .filter((t) => t.wikidata_id)
    .map((t) => ({ qid: t.wikidata_id, title: t.label_en, from: null, to: null, editions: t.editions.length, href: paths.differences(t.wikidata_id) }))
}

/** Prepared topics (from /api/topics) and the example block. */
export async function loadStart(api: Client): Promise<Result<StartVM>> {
  const r = await api.topics()
  if (!r.ok) return r
  const prepared = toPrepared(r.data)
  const winter = r.data.topics.find((t) => t.wikidata_id === EXAMPLE_QID)
  let example: StartVM['example'] = null
  if (winter) {
    const c = await api.compare({ topic: winter.topic_id, h: EXAMPLE_STATEMENT.h })
    if (c.ok) example = toExample(c.data, { qid: EXAMPLE_QID, topicId: winter.topic_id, title: winter.label_en })
  }
  return { ok: true, data: { prepared, example } }
}

/**
 * The example is hand-picked, so each edition gets a hand-picked clause: a part of its live English text
 * (gloss, or the English text itself) and the phrase in it that differs. Nothing is reworded: the clause
 * and the phrase are only searched in the live text, and an edition whose clause is not there shows its
 * whole text, marked where the phrase is found.
 */
export const EXAMPLE_CLAUSES: { lang: Lang; clause: string; mark: string }[] = [
  { lang: 'fi', clause: 'the Soviet Union staged the Shelling of Mainila', mark: 'staged' },
  { lang: 'sv', clause: 'The official Soviet explanation for the attack referred to the above-mentioned shelling of Mainila', mark: 'The official Soviet explanation' },
  { lang: 'en', clause: 'an incident was reported near the Soviet village of Mainila', mark: 'was reported' },
  { lang: 'ru', clause: 'the Soviet Union organized a provocation', mark: 'organized a provocation' },
]

function englishOf(lang: string, cell: CellRaw): string | null {
  return cell.gloss ?? (lang === 'en' ? cell.text : null)
}

/** Marks the first occurrence of each word, case-insensitively, and only when the words are really there. */
function markIn(text: string, words: string[]): MarkedText {
  const spans = words
    .filter(Boolean)
    .map((w) => {
      const i = text.toLowerCase().indexOf(w.toLowerCase())
      return i < 0 ? null : { start: i, end: i + w.length }
    })
    .filter((x): x is { start: number; end: number } => x !== null)
  return { text, spans }
}

/** The clause as it stands in the live text (first letter raised), or the whole text when it is not there. */
export function clauseOf(text: string, clause: string): string {
  const i = text.toLowerCase().indexOf(clause.toLowerCase())
  if (i < 0) return text
  return capital(text.slice(i, i + clause.length))
}

/** Finnish plus the curated editions that are in the data; null when fewer than two others are. */
export function toExample(raw: CompareRes, topic: TopicRef): StartVM['example'] {
  const row = raw.rows[0]
  const fi = row?.cells[raw.anchor]
  if (!row || !fi?.h || !fi.page_id) return null
  const lines: ExampleLine[] = []
  for (const c of EXAMPLE_CLAUSES) {
    const cell = row.cells[c.lang]
    const text = cell && (c.lang === raw.anchor || cell.status === 'matched') ? englishOf(c.lang, cell) : null
    if (!text) continue
    lines.push({ lang: c.lang, say: markIn(clauseOf(text, c.clause), [c.mark]) })
  }
  if (lines[0]?.lang !== raw.anchor || lines.length < 3) return null
  return {
    topic,
    title: exampleTitle(lines.length),
    lines,
    href: paths.statement(topic.qid, raw.anchor, fi.page_id, fi.h),
  }
}

/** Wikidata descriptions often start lowercase; the UI writes sentence case. */
export function capital(s: string): string {
  return s ? s[0].toUpperCase() + s.slice(1) : s
}

export function toResult(r: SearchResultRaw): SearchResult {
  const href = r.status === 'ready' ? paths.differences(r.qid) : r.status === 'no_finnish' ? null : paths.ingest(r.qid)
  return { qid: r.qid, title: r.title, description: capital(r.description ?? ''), status: r.status, etaS: r.eta_s, href }
}

/** GET /api/search?q. */
export async function loadSearch(api: Client, q: string): Promise<Result<SearchVM>> {
  if (!q.trim()) return { ok: true, data: { q, results: [] } }
  const r = await api.search(q.trim())
  if (!r.ok) return r
  return { ok: true, data: { q, results: r.data.results.slice(0, 6).map(toResult) } }
}

function isLang(x: string): x is Lang {
  return (LANGS as readonly string[]).includes(x)
}

export function toIngest(raw: IngestRes, now: Date = new Date()): IngestVM {
  const byLang = new Map(raw.editions.map((e) => [e.lang, e]))
  const editions: IngestEdition[] = LANGS.map((lang) => {
    const e = byLang.get(lang)
    if (!e) return { lang, state: 'waiting', pct: 0, error: null, retryAt: null }
    const pct = e.state === 'done' ? 100 : Math.max(0, Math.min(100, Math.round(e.pct ?? 0)))
    return { lang, state: e.state, pct, error: e.error ?? null, retryAt: e.retry_at ?? null }
  })
  const extra = raw.editions.filter((e) => !isLang(e.lang))
  if (extra.length) console.warn('ingest: unknown editions ignored', extra.map((e) => e.lang))
  const done = raw.state === 'done'
  // Editions without an article never load, so they do not count towards the bar.
  const live = editions.filter((e) => e.error !== 'no_article')
  const progress = done || !live.length ? 100 : Math.round(live.reduce((s, e) => s + e.pct, 0) / live.length)
  const year = now.getUTCFullYear()
  const fromYear = year - FASTER_YEARS
  return {
    qid: raw.qid,
    title: raw.title,
    state: raw.state,
    progress,
    etaS: done ? null : raw.eta_s,
    editions,
    readyCount: editions.filter((e) => e.state === 'done').length,
    openHref: raw.state === 'usable' || done ? paths.differences(raw.qid) : null,
    faster: raw.since || done || raw.state === 'failed' || (raw.eta_s !== null && raw.eta_s <= FASTER_HIDE_S) ? null : { fromYear, toYear: year, since: `${fromYear}-01-01`, etaS: FASTER_ETA_S },
  }
}

/** POST /api/ingest. */
export async function startIngest(api: Client, qid: string, since?: string): Promise<Result<IngestVM>> {
  const r = await api.startIngest(since ? { qid, since } : { qid })
  if (!r.ok) return r
  return { ok: true, data: toIngest(r.data) }
}

/** GET /api/ingest/:qid. A finished job makes the topic list stale, so the cache is dropped. */
export async function loadIngest(api: Client, qid: string): Promise<Result<IngestVM>> {
  const r = await api.ingest(qid)
  if (!r.ok) return r
  if (r.data.state === 'usable' || r.data.state === 'done') forgetTopics()
  return { ok: true, data: toIngest(r.data) }
}
