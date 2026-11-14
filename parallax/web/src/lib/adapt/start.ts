// Start page, search and ingest: raw API -> view model. Owner: P1.
import type { api as Api } from '../api/client'
import type { IngestRes, SearchResultRaw, TopicsRes } from '../api/types'
import { start as fixtureStart } from '../fixture'
import { LANGS, type IngestEdition, type IngestVM, type Lang, type Result, type SearchResult, type SearchVM, type StartVM } from '../model'
import { paths } from '../router.svelte'
import { forgetTopics } from './shared'

type Client = typeof Api

/** The example block links to this real seed v4 statement (Finnish: the Soviet Union staged the Mainila shots). */
export const EXAMPLE_QID = 'Q134949'
export const EXAMPLE_STATEMENT = { lang: 'fi', pageId: 1256, h: 'abe24bc5f22fda02' }

/** "Faster" offers the last five years; the API gives no estimate for it, so it is a fixed guess. */
const FASTER_YEARS = 5
const FASTER_ETA_S = 60

export function toPrepared(raw: TopicsRes): StartVM['prepared'] {
  // The topics list carries no year span, so years stay empty in live mode.
  return raw.topics
    .filter((t) => t.wikidata_id)
    .map((t) => ({ qid: t.wikidata_id, title: t.label_en, from: null, to: null, href: paths.differences(t.wikidata_id) }))
}

/** Prepared topics (from /api/topics) and the example block. */
export async function loadStart(api: Client): Promise<Result<StartVM>> {
  const r = await api.topics()
  if (!r.ok) return r
  const prepared = toPrepared(r.data)
  // The example text is the fixture's (the API has no English mark words); shown only when Winter War is loaded.
  const fx = fixtureStart()
  const winter = prepared.find((p) => p.qid === EXAMPLE_QID)
  const example =
    winter && fx.ok && fx.data.example
      ? {
          ...fx.data.example,
          topic: { ...fx.data.example.topic, title: winter.title },
          href: paths.statement(EXAMPLE_QID, EXAMPLE_STATEMENT.lang, EXAMPLE_STATEMENT.pageId, EXAMPLE_STATEMENT.h),
        }
      : null
  return { ok: true, data: { prepared, example } }
}

export function toResult(r: SearchResultRaw): SearchResult {
  const href = r.status === 'ready' ? paths.differences(r.qid) : r.status === 'no_finnish' ? null : paths.ingest(r.qid)
  return { qid: r.qid, title: r.title, description: r.description ?? '', status: r.status, etaS: r.eta_s, href }
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
  const progress = done ? 100 : Math.round(editions.reduce((s, e) => s + e.pct, 0) / editions.length)
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
    faster: raw.since || done || raw.state === 'failed' ? null : { fromYear, toYear: year, since: `${fromYear}-01-01`, etaS: FASTER_ETA_S },
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
