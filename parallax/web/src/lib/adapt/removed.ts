// Removed tab: /api/dropped -> view model. Owner: P3.
// The API pages at most 200 rows, a topic has a few hundred, so the adapter loads them all once per
// topic and filters (edition, text, date) and pages on the client. The tab count and the list then
// always agree.
import type { api as Api } from '../api/client'
import type { DroppedRowRaw } from '../api/types'
import { excerpt, note, noteText, quote, removedNote, stillIn } from '../copy'
import { LANGS, type Lang, type MarkedText, type RemovedRow, type RemovedVM, type Result } from '../model'
import { paths } from '../router.svelte'
import type { TopicCtx, WithoutCounts } from './shared'

type Client = typeof Api

export const PAGE = 25
const API_LIMIT = 200
/** Longest cut quoted in the note ("removed “staged”"); a longer cut in the middle is quoted shortened. */
const QUOTE_MAX = 40

const cache = new Map<string, Promise<Result<DroppedRowRaw[]>>>()

async function fetchAll(api: Client, topicId: string): Promise<Result<DroppedRowRaw[]>> {
  const first = await api.dropped({ topic: topicId, limit: API_LIMIT, offset: 0 })
  if (!first.ok) return first
  const rows: DroppedRowRaw[] = [...first.data.rows]
  while (rows.length < first.data.total) {
    const next = await api.dropped({ topic: topicId, limit: API_LIMIT, offset: rows.length })
    if (!next.ok) return next
    if (!next.data.rows.length) break
    rows.push(...next.data.rows)
  }
  return { ok: true, data: rows }
}

function allRows(api: Client, topicId: string): Promise<Result<DroppedRowRaw[]>> {
  let p = cache.get(topicId)
  if (!p) {
    p = fetchAll(api, topicId).then((r) => {
      if (!r.ok) cache.delete(topicId)
      return r
    })
    cache.set(topicId, p)
  }
  return p
}

/** Test hook. */
export function forgetRemoved(): void {
  cache.clear()
}

const isLang = (x: string): x is Lang => (LANGS as readonly string[]).includes(x)

/** On a past date only what was already removed by then counts (the API knows today's list only). */
function onDate(rows: DroppedRowRaw[], date: string | null): DroppedRowRaw[] {
  return date ? rows.filter((r) => r.died !== null && r.died.slice(0, 10) <= date) : rows
}

/** A partial cut; `words_en` is the English gloss of the removed words (dropped.py), null without one. */
type Cut = { start: number; end: number; words_en?: string | null }

/** The statement with its removed part struck, and what the note says was removed. */
export function cutOf(r: Pick<DroppedRowRaw, 'text' | 'gloss' | 'removed'>): {
  say: MarkedText
  what: 'all' | 'end' | { words: string }
} {
  const cut: Cut | null | undefined = r.removed
  if (!cut) {
    const text = r.gloss ?? r.text
    return { say: { text, spans: [{ start: 0, end: text.length }] }, what: 'all' }
  }
  const atEnd = cut.end >= r.text.length
  const words = r.text.slice(cut.start, cut.end).replace(/[\s,;:]+$/, '')
  // The English gloss translates the whole sentence, so the cut's offsets do not carry over. With a gloss
  // the English sentence is shown and the removed words are struck where their own gloss is found in it.
  if (r.gloss) {
    const en = cut.words_en?.replace(/[\s.,;:]+$/, '') ?? null
    const at = en ? r.gloss.toLowerCase().indexOf(en.toLowerCase()) : -1
    const spans = at >= 0 && en ? [{ start: at, end: at + en.length }] : []
    const say = { text: r.gloss, spans }
    if (atEnd) return { say, what: 'end' }
    return { say, what: { words: excerpt(en ?? words, QUOTE_MAX) } }
  }
  const say = { text: r.text, spans: [{ start: cut.start, end: cut.end }] }
  if (atEnd) return { say, what: 'end' }
  return { say, what: { words: excerpt(words, QUOTE_MAX) } }
}

export function toRow(qid: string, r: DroppedRowRaw): RemovedRow {
  const { say, what } = cutOf(r)
  const alive = r.alive_in.map((a) => a.lang).filter(isLang)
  return {
    id: `${r.lang}:${r.page_id}:${r.h}`,
    say,
    note: note(removedNote(r.lang, what, r.died ?? '', r.time_precision !== 'snapshot'), alive.length ? [{ text: stillIn(alive) }] : []),
    href: paths.statement(qid, r.lang, r.page_id, r.h),
  }
}

function matches(r: DroppedRowRaw, q: string, row: RemovedRow): boolean {
  if (!q) return true
  const hay = [r.text, r.gloss ?? '', noteText(row.note), ...r.alive_in.map((a) => a.text)].join('\n').toLowerCase()
  return hay.includes(q)
}

/** /api/dropped?topic -> rows. offset = rows already shown; the result holds them plus one more page. */
export async function loadRemoved(
  api: Client,
  ctx: TopicCtx,
  opts: { q: string; offset: number; edition: Lang | null },
): Promise<Result<WithoutCounts<RemovedVM>>> {
  const all = await allRows(api, ctx.topic.topicId)
  if (!all.ok) return all
  const dated = onDate(all.data, ctx.date)
  const editions = LANGS.filter((l) => dated.some((r) => r.lang === l))
  const q = opts.q.trim().toLowerCase()
  const found = dated
    .filter((r) => !opts.edition || r.lang === opts.edition)
    .map((r) => ({ r, row: toRow(ctx.topic.qid, r) }))
    .filter(({ r, row }) => matches(r, q, row))
  const shown = found.slice(0, Math.max(PAGE, opts.offset + PAGE)).map((x) => x.row)
  return {
    ok: true,
    data: {
      topic: ctx.topic,
      date: ctx.date,
      q: opts.q,
      edition: opts.edition,
      editions,
      rows: shown,
      total: found.length,
      more: found.length - shown.length,
    },
  }
}

/** The Removed tab count on ctx.date: every statement removed by then. */
export async function countRemoved(api: Client, ctx: TopicCtx): Promise<number | null> {
  const all = await allRows(api, ctx.topic.topicId)
  return all.ok ? onDate(all.data, ctx.date).length : null
}
