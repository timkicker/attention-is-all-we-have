// Differences tab and one statement: raw API -> view model. Owner: P2.
//
// What counts as "says it differently": the judge paired the edition's sentence with the Finnish
// statement and either called it contradicting, or partial while naming a number or term that differs.
// A nearest sentence nobody compared, or a partial match with nothing named, is never shown as a
// difference. Editions with no matching sentence at all are "Not in <edition>".

import type { api as Api } from '../api/client'
import type { CellRaw, CompareRes, CompareRowRaw, LifeRaw, MarkRaw, TopicsRes } from '../api/types'
import * as copy from '../copy'
import { fmtNum } from '../format'
import { plain } from '../marks'
import { LANGS } from '../model'
import type {
  DiffRow,
  DifferencesVM,
  Lang,
  MarkedText,
  Note,
  Result,
  Span,
  StatementChange,
  StatementGroup,
  StatementVM,
} from '../model'
import { paths } from '../router.svelte'
import type { TopicCtx, WithoutCounts } from './shared'

type Client = typeof Api

export type Mark = MarkRaw
export type Cell = CellRaw
export type Row = CompareRowRaw
export type Life = LifeRaw

export const PAGE = 25
const MORE_STEP = 100
const FETCH = 200
const MATCHED = new Set(['same', 'partial', 'contradicts'])

const isLang = (x: string): x is Lang => (LANGS as readonly string[]).includes(x)
const byOrder = (a: string, b: string) => LANGS.indexOf(a as Lang) - LANGS.indexOf(b as Lang)

// ---------- Numbers ----------

const NUM = /\d{1,3}(?:[   .,]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?/g

/** "25 904" / "25.904" / "25,904" -> 25904; "2,5" -> 2.5. */
export function numValue(raw: string): number | null {
  const s = raw.trim()
  if (/^\d{1,3}(?:[   .,]\d{3})+$/.test(s)) return Number(s.replace(/[   .,]/g, ''))
  const m = /^(\d{1,3}(?:[   .,]\d{3})+)([.,]\d+)$/.exec(s)
  if (m) return Number(m[1].replace(/[   .,]/g, '') + '.' + m[2].slice(1))
  const v = Number(s.replace(',', '.'))
  return Number.isFinite(v) ? v : null
}

export function numbersIn(text: string): { value: number; start: number; end: number }[] {
  const out: { value: number; start: number; end: number }[] = []
  for (const m of text.matchAll(NUM)) {
    const v = numValue(m[0])
    if (v !== null) out.push({ value: v, start: m.index ?? 0, end: (m.index ?? 0) + m[0].length })
  }
  return out
}

const HEDGES: [RegExp, string][] = [
  [/\b(rund|etwa|ca\.?|circa|cirka|omkring|ungefär|noin|umbes|about|approximately|around)\b|около|приблизно|близько|примерно/i, copy.topic.ABOUT],
  [/\b(bis zu|up to|jopa|kuni)\b|(^|\s)до\s/i, copy.topic.UP_TO],
  [/\b(über|over|yli|över|üle)\b|более|свыше|понад|больше/i, copy.topic.OVER],
]

/** The other edition's number as English text: "rund 25.000" -> "about 25,000"; null when it has no number. */
export function numberText(other: string): string | null {
  const ns = numbersIn(other)
  if (!ns.length) return null
  const pct = /%|procent|prozent|percent|prosent|protsent|процент/i.test(other) ? copy.topic.PERCENT : ''
  let body = fmtNum(ns[0].value)
  if (ns.length >= 2 && /[–—-]/.test(other.slice(ns[0].end, ns[1].start))) body = `${fmtNum(ns[0].value)}–${fmtNum(ns[1].value)}`
  const hedge = HEDGES.find(([re]) => re.test(other))?.[1]
  return `${hedge ? `${hedge} ` : ''}${body}${pct}`
}

// ---------- Marks on the English text ----------

const real = (s: string | null | undefined) => !!s && s.trim() !== '' && s.trim() !== 'None'

/** Marks that name something: a number or term on both sides (the judge writes "None" for an absent side). */
export function namedMarks(c: Cell): Mark[] {
  return (c.marks ?? []).filter((m) => real(m.this) && real(m.other))
}

/** Spans in an English text for the Finnish side of these marks: numbers by value, terms by their English word. */
export function spansFor(text: string, marks: Mark[]): Span[] {
  const spans: Span[] = []
  const nums = numbersIn(text)
  const lower = text.toLowerCase()
  for (const m of marks) {
    if (m.kind === 'number') {
      for (const v of numbersIn(m.this)) {
        const hit = nums.find((n) => n.value === v.value)
        if (hit) spans.push({ start: hit.start, end: hit.end })
      }
    } else {
      for (const w of [m.this_en, m.this]) {
        if (!real(w)) continue
        const i = lower.indexOf(w!.toLowerCase())
        if (i >= 0) {
          spans.push({ start: i, end: i + w!.length })
          break
        }
      }
    }
  }
  return mergeSpans(spans)
}

/** Spans in another edition's own text for its side of the marks (exact words). */
export function otherSpans(text: string, marks: Mark[]): Span[] {
  const spans: Span[] = []
  const lower = text.toLowerCase()
  for (const m of marks) {
    for (const part of m.other.split(/\s*(?:\.\.\.|…)\s*/)) {
      if (!real(part)) continue
      const i = lower.indexOf(part.toLowerCase())
      if (i >= 0) spans.push({ start: i, end: i + part.length })
      else if (m.kind === 'number') {
        const nums = numbersIn(text)
        for (const v of numbersIn(part)) {
          const hit = nums.find((n) => n.value === v.value)
          if (hit) spans.push({ start: hit.start, end: hit.end })
        }
      }
    }
  }
  return mergeSpans(spans)
}

export function mergeSpans(spans: Span[]): Span[] {
  const s = [...spans].sort((a, b) => a.start - b.start)
  const out: Span[] = []
  for (const x of s) {
    const last = out[out.length - 1]
    if (last && x.start <= last.end) last.end = Math.max(last.end, x.end)
    else out.push({ ...x })
  }
  return out
}

// ---------- One row ----------

export type Kind = 'differs' | 'same' | 'missing' | 'open' | 'absent'

/** How one edition relates to the Finnish statement. `present` = the edition had an article on the date. */
export function kindOf(c: Cell | undefined, present: boolean): Kind {
  if (!present) return 'absent'
  if (!c || c.status === 'not_found') return 'missing'
  if (c.status !== 'matched' || !c.verdict || !MATCHED.has(c.verdict.label)) return 'open'
  if (c.verdict.label === 'contradicts') return 'differs'
  if (c.verdict.label === 'partial') return namedMarks(c).length ? 'differs' : 'open'
  return 'same'
}

export interface Analysed {
  id: string
  lang: Lang
  pageId: number
  h: string
  say: MarkedText
  original: string
  note: Note
  differs: Lang[]
  contradicts: number
  newest: string
}

/** Edition start dates from /api/topics, YYYY-MM-DD per lang. */
export type Starts = Partial<Record<Lang, string>>

export function analyse(row: Row, anchor: string, present: Set<string>, starts: Starts): Analysed | null {
  const a = row.cells[anchor]
  if (!a || !a.h || a.page_id === null) return null
  const others = Object.keys(row.cells).filter((l) => l !== anchor && isLang(l)).sort(byOrder) as Lang[]
  const kinds = new Map(others.map((l) => [l, kindOf(row.cells[l], present.has(l))]))
  const differs = others.filter((l) => kinds.get(l) === 'differs')
  if (!differs.length) return null
  const missing = others.filter((l) => kinds.get(l) === 'missing')
  const same = others.filter((l) => kinds.get(l) === 'same')
  const counted = others.filter((l) => kinds.get(l) !== 'absent')

  const text = readable(a.gloss ?? a.text ?? '', row.section)
  const marks = differs.flatMap((l) => namedMarks(row.cells[l]))

  // numbers first, grouped by the value the edition gives; then the editions that differ in words
  const byValue = new Map<string, Lang[]>()
  const wordy: Lang[] = []
  for (const l of differs) {
    const n = namedMarks(row.cells[l]).find((m) => m.kind === 'number' && numberText(m.other))
    if (n) {
      const v = numberText(n.other)!
      byValue.set(v, [...(byValue.get(v) ?? []), l])
    } else wordy.push(l)
  }
  const parts: Note[] = [...byValue].map(([v, ls]) => copy.saysValueNote(ls, v))
  if (wordy.length) parts.push(copy.saysDifferentlyNote(wordy))

  // "English changed it in 2009": the newest differing wording that appeared after the edition's article began
  const changed = differs
    .map((l) => ({ l, born: row.cells[l].born ?? '' }))
    .filter((x) => x.born && starts[x.l] && x.born.slice(0, 10) > addDays(starts[x.l]!, 30))
    .sort((x, y) => (x.born < y.born ? 1 : -1))[0]
  if (changed) parts.push([{ text: copy.changedItIn(changed.l, changed.born.slice(0, 4)) }])
  if (missing.length) parts.push([{ text: copy.notIn(missing) }])
  if (same.length) {
    const rest = counted.length - differs.length - missing.length
    parts.push([{ text: same.length === rest ? copy.sameInOthers(same.length) : copy.sameIn(same) }])
  }

  return {
    id: row.row_id,
    lang: anchor as Lang,
    pageId: a.page_id,
    h: a.h,
    say: { text, spans: spansFor(text, marks) },
    original: a.text ?? '',
    note: copy.note(...parts),
    differs,
    contradicts: differs.filter((l) => row.cells[l].verdict?.label === 'contradicts').length,
    newest: differs.map((l) => row.cells[l].born ?? '').sort().pop() ?? '',
  }
}

/** Infobox rows read "losses1: 25,904 fallen"; the field name is not part of what the edition says. */
export function readable(text: string, section: string): string {
  return section === '[infobox]' ? text.replace(/^[\p{L}_ ]{1,30}\d*:\s+/u, '') : text
}

function addDays(day: string, n: number): string {
  const d = new Date(`${day.slice(0, 10)}T00:00:00Z`)
  d.setUTCDate(d.getUTCDate() + n)
  return d.toISOString().slice(0, 10)
}

/** Most editions differing first, then most contradicting, then the newest wording. */
export function rank(rows: Analysed[]): Analysed[] {
  return [...rows].sort(
    (x, y) =>
      y.differs.length - x.differs.length || y.contradicts - x.contradicts || (x.newest < y.newest ? 1 : x.newest > y.newest ? -1 : 0),
  )
}

export function matches(r: Analysed, q: string): boolean {
  const s = q.trim().toLowerCase()
  return !s || r.say.text.toLowerCase().includes(s) || r.original.toLowerCase().includes(s)
}

// ---------- Loading (cached per topic and date) ----------

interface Loaded {
  rows: Analysed[]
  starts: Starts
}

const cache = new Map<string, Promise<Result<Loaded>>>()
let topicsCache: Promise<Result<TopicsRes>> | null = null

async function topicStarts(api: Client, topicId: string): Promise<Starts> {
  topicsCache ??= api.topics()
  const r = await topicsCache
  if (!r.ok) {
    topicsCache = null
    return {}
  }
  const t = r.data.topics.find((x) => x.topic_id === topicId)
  const out: Starts = {}
  for (const e of t?.editions ?? []) if (isLang(e.lang) && e.first_ts) out[e.lang] = e.first_ts.slice(0, 10)
  return out
}

/** Every Finnish statement of the date through /api/compare, in pages of 200 fetched side by side. */
async function compareAll(api: Client, topic: string, asOf: string | null): Promise<Result<CompareRes>> {
  const q = { topic, as_of: asOf ?? undefined, limit: FETCH }
  const first = await api.compare({ ...q, offset: 0 })
  if (!first.ok) return first
  const rest = await Promise.all(
    Array.from({ length: Math.ceil(first.data.total_rows / FETCH) - 1 }, (_, i) => api.compare({ ...q, offset: (i + 1) * FETCH })),
  )
  const rows = [...first.data.rows]
  for (const r of rest) {
    if (!r.ok) return r
    rows.push(...r.data.rows)
  }
  return { ok: true, data: { ...first.data, rows } }
}

function load(api: Client, ctx: TopicCtx): Promise<Result<Loaded>> {
  const key = `${ctx.topic.topicId}|${ctx.date ?? ''}`
  let p = cache.get(key)
  if (!p) {
    p = (async (): Promise<Result<Loaded>> => {
      const [cmp, starts] = await Promise.all([compareAll(api, ctx.topic.topicId, ctx.date), topicStarts(api, ctx.topic.topicId)])
      if (!cmp.ok) return cmp
      const present = new Set(Object.keys(cmp.data.editions))
      const rows = cmp.data.rows
        .map((r) => analyse(r, cmp.data.anchor, present, starts))
        .filter((x): x is Analysed => x !== null)
      return { ok: true, data: { rows: rank(rows), starts } }
    })()
    cache.set(key, p)
    p.then((r) => {
      if (!r.ok) cache.delete(key)
    })
  }
  return p
}

/** /api/compare (as_of = ctx.date) -> rows that differ. offset = rows the page already shows. */
export async function loadDifferences(
  api: Client,
  ctx: TopicCtx,
  opts: { q: string; offset: number },
): Promise<Result<WithoutCounts<DifferencesVM>>> {
  const r = await load(api, ctx)
  if (!r.ok) return r
  const { rows, starts } = r.data
  const date = ctx.date
  const missing = date ? (LANGS.filter((l) => starts[l] && starts[l]! > date) as Lang[]) : []
  if (date && starts.fi && date < starts.fi) {
    return {
      ok: true,
      data: { topic: ctx.topic, date, past: { date, missing }, q: opts.q, rows: [], total: 0, more: 0, beforeArticle: { lang: 'fi', startsOn: starts.fi } },
    }
  }
  const hits = rows.filter((x) => matches(x, opts.q))
  const size = opts.offset ? MORE_STEP : PAGE
  const shown = hits.slice(opts.offset, opts.offset + size)
  const left = hits.length - opts.offset - shown.length
  return {
    ok: true,
    data: {
      topic: ctx.topic,
      date,
      past: date ? { date, missing } : null,
      q: opts.q,
      rows: shown.map((x): DiffRow => ({ id: x.id, say: x.say, note: x.note, href: paths.statement(ctx.topic.qid, x.lang, x.pageId, x.h) })),
      total: hits.length,
      more: Math.min(left, MORE_STEP),
      beforeArticle: null,
    },
  }
}

/** How many statements differ on the date (the Differences tab count). */
export async function countDifferences(api: Client, ctx: TopicCtx): Promise<number | null> {
  const r = await load(api, ctx)
  return r.ok ? r.data.rows.length : null
}

// ---------- One statement ----------


const words = (s: string) => s.split(/\s+/).filter(Boolean)
const norm = (w: string) => w.toLowerCase().replace(/[^\p{L}\p{N}]/gu, '')

/** Word overlap of two sentences, 0..1. */
export function overlap(a: string, b: string): number {
  const x = new Set(words(a).map(norm).filter(Boolean))
  const y = new Set(words(b).map(norm).filter(Boolean))
  if (!x.size || !y.size) return 0
  let n = 0
  for (const w of x) if (y.has(w)) n++
  return n / Math.max(x.size, y.size)
}

/** The words that changed between two versions, with one word of context when only words were added or cut. */
export function changedWords(from: string, to: string): { from: string; to: string } | null {
  const a = words(from)
  const b = words(to)
  const same = (x: string, y: string) => norm(x) === norm(y)
  let p = 0
  while (p < a.length && p < b.length && same(a[p], b[p])) p++
  let s = 0
  while (s < a.length - p && s < b.length - p && same(a[a.length - 1 - s], b[b.length - 1 - s])) s++
  let x = a.slice(p, a.length - s)
  let y = b.slice(p, b.length - s)
  if (x.map(norm).join('') === y.map(norm).join('')) return null
  if ((!x.length || !y.length) && p > 0) {
    x = a.slice(p - 1, a.length - s)
    y = b.slice(p - 1, b.length - s)
  }
  if (!x.length || !y.length) {
    x = a.slice(p, a.length - s + 1)
    y = b.slice(p, b.length - s + 1)
  }
  return { from: copy.excerpt(x.join(' '), 90), to: copy.excerpt(y.join(' '), 90) }
}

/** Strips the "/* Section *\/" prefix MediaWiki puts in edit comments. */
export function cleanComment(c: string | null): string | null {
  const s = (c ?? '').replace(/\/\*.*?\*\//g, '').replace(/\s+/g, ' ').trim()
  return s || null
}

/**
 * Edits of the sentences the judge paired with the statement: from each paired life, step back to the life it
 * replaced (removed in the revision that added it, mostly the same words) and report what changed.
 */
export function changesOf(lives: Life[], ownLang: string): StatementChange[] {
  const out = new Map<string, StatementChange>()
  const paired = lives.filter((l) => l.lang !== ownLang && l.verdict && MATCHED.has(l.verdict.label))
  for (const start of paired) {
    let cur: Life | undefined = start
    for (let guard = 0; cur && guard < 50; guard++) {
      const c: Life = cur
      const prev = lives.find((l) => l.lang === c.lang && l !== c && l.died_rev === c.born_rev && overlap(l.text, c.text) >= 0.5)
      if (!prev) break
      const useGloss = !!(prev.gloss && c.gloss)
      const diff = changedWords(useGloss ? prev.gloss! : prev.text, useGloss ? c.gloss! : c.text)
      const key = `${c.lang}|${c.born_rev}`
      if (diff && isLang(c.lang) && !out.has(key)) {
        out.set(key, {
          date: (c.born ?? '').slice(0, 10),
          lang: c.lang,
          from: diff.from,
          to: diff.to,
          comment: cleanComment(prev.died_comment),
          url: oldid(c.lang, c.born_rev),
          approx: c.time_precision === 'snapshot',
        })
      }
      cur = prev
    }
  }
  return [...out.values()].sort((x, y) => (x.date < y.date ? 1 : x.date > y.date ? -1 : 0))
}

const oldid = (lang: string, rev: number | null) => (rev ? `https://${lang}.wikipedia.org/w/index.php?oldid=${rev}` : null)

export function statementOf(row: Row | null, anchor: string, present: Set<string>, fallback: { lang: string; text: string; gloss: string | null }) {
  if (!row) {
    const text = fallback.gloss ?? fallback.text
    return {
      title: text,
      groups: [{ langs: [fallback.lang as Lang], say: plain(text), originals: [], marked: [] }] as StatementGroup[],
      missing: [] as Lang[],
      open: [] as Lang[],
    }
  }
  const a = row.cells[anchor]
  const others = Object.keys(row.cells).filter((l) => l !== anchor && isLang(l)).sort(byOrder) as Lang[]
  const kinds = new Map(others.map((l) => [l, kindOf(row.cells[l], present.has(l))]))
  const differs = others.filter((l) => kinds.get(l) === 'differs')
  const allMarks = differs.flatMap((l) => namedMarks(row.cells[l]))
  const text = readable(a.gloss ?? a.text ?? '', row.section)
  const orig = (l: Lang, c: Cell, spans: Span[]) => ({ lang: l, say: { text: c.text ?? '', spans }, url: c.oldid_url })
  const anchorSpans = spansFor(a.text ?? '', allMarks.map((m) => ({ ...m, this_en: null })))
  const first: StatementGroup = {
    langs: [anchor as Lang],
    say: { text, spans: spansFor(text, allMarks) },
    originals: [{ lang: anchor as Lang, text: a.text ?? '', url: a.oldid_url }],
    marked: [orig(anchor as Lang, a, anchorSpans)],
  }
  const groups: StatementGroup[] = [first]
  for (const l of others) {
    const c = row.cells[l]
    const k = kinds.get(l)
    if (k === 'same') {
      first.langs.push(l)
      first.originals.push({ lang: l, text: c.text ?? '', url: c.oldid_url })
      first.marked.push(orig(l, c, []))
    } else if (k === 'differs' || (k === 'open' && c.status === 'matched')) {
      const marks = k === 'differs' ? namedMarks(c) : []
      const english = c.gloss ?? c.text ?? ''
      const spans = l === 'en' ? otherSpans(english, marks) : numberSpans(english, marks)
      const say = { text: english, spans }
      const twin = groups.find((g, i) => i > 0 && g.say.text === english)
      if (twin) {
        twin.langs.push(l)
        twin.originals.push({ lang: l, text: c.text ?? '', url: c.oldid_url })
        twin.marked.push(orig(l, c, otherSpans(c.text ?? '', marks)))
      } else {
        groups.push({ langs: [l], say, originals: [{ lang: l, text: c.text ?? '', url: c.oldid_url }], marked: [orig(l, c, otherSpans(c.text ?? '', marks))] })
      }
    }
  }
  return {
    title: text,
    groups,
    missing: others.filter((l) => kinds.get(l) === 'missing'),
    open: others.filter((l) => kinds.get(l) === 'open' && row.cells[l].status !== 'matched'),
  }
}

/** Spans in an English gloss for the other side's numbers (terms are in the edition's language, not findable). */
function numberSpans(text: string, marks: Mark[]): Span[] {
  const nums = numbersIn(text)
  const spans: Span[] = []
  for (const m of marks) {
    if (m.kind !== 'number') continue
    for (const v of numbersIn(m.other)) {
      const hit = nums.find((n) => n.value === v.value)
      if (hit) spans.push({ start: hit.start, end: hit.end })
    }
  }
  return mergeSpans(spans)
}

/** /api/compare for this one statement (h filter) + /api/claim/:lang/:pageId/:h/timeline. */
export async function loadStatement(
  api: Client,
  ctx: TopicCtx,
  lang: string,
  pageId: string,
  h: string,
): Promise<Result<WithoutCounts<StatementVM>>> {
  const [cmp, tl] = await Promise.all([
    api.compare({ topic: ctx.topic.topicId, as_of: ctx.date ?? undefined, anchor: lang, h, limit: 1 }),
    api.timeline(lang, pageId, h),
  ])
  if (!tl.ok) return tl
  if (!cmp.ok) return cmp
  const lives = tl.data.lives
  const own = lives.filter((l) => l.lang === lang && l.h === h)
  const row = cmp.data.rows.find((r) => r.cells[lang]?.h === h) ?? null
  const present = new Set(Object.keys(cmp.data.editions))
  const s = statementOf(row, cmp.data.anchor, present, { lang, text: tl.data.claim.text, gloss: own[own.length - 1]?.gloss ?? null })
  const vm: WithoutCounts<StatementVM> = {
    topic: ctx.topic,
    date: ctx.date,
    title: copy.excerpt(s.title, 80),
    groups: s.groups,
    missing: s.missing,
    open: s.open,
    changes: changesOf(lives, lang).slice(0, 8),
    backHref: paths.differences(ctx.topic.qid),
  }
  return { ok: true, data: vm }
}
