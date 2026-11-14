// Differences tab and one statement: raw API -> view model. Owner: P2.
//
// What counts as "says it differently": the judge paired the edition's sentence with the Finnish
// statement and either called it contradicting, or partial while naming a number or term that differs.
// A nearest sentence nobody compared, or a partial match with nothing named, is never shown as a
// difference. Editions with no matching sentence at all are "Not in <edition>".

import type { api as Api } from '../api/client'
import type { CellRaw, CompareRes, CompareRowRaw, DroppedRowRaw, LifeRaw, MarkRaw, TopicsRes } from '../api/types'
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

/** The list opens with a few rows; "Show N more" then shows the rest. */
export const PAGE = 5
const MORE_STEP = 1000
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

/**
 * Both sides of a number mark measure the same thing: the other number is within the same order of magnitude
 * (ratio 0.2 to 5). "422" against "48,745" is a different count, so the note says "says it differently".
 */
export function comparable(m: { this: string; other: string }): boolean {
  const a = numbersIn(m.this)[0]?.value
  const b = numbersIn(m.other)[0]?.value
  if (a === undefined || b === undefined || a === 0) return false
  const r = b / a
  return r >= 0.2 && r <= 5
}

// ---------- Marks on the English text ----------

const real = (s: string | null | undefined) => !!s && s.trim() !== '' && s.trim() !== 'None'

/** Marks that name something: a number or term on both sides (the judge writes "None" for an absent side). */
export function namedMarks(c: Cell): Mark[] {
  return (c.marks ?? []).filter((m) => real(m.this) && real(m.other) && !(m.kind === 'number' && agrees(m)))
}

/** A number mark whose two sides agree after rounding: within 3%, or equal at the rounder number's precision. */
export function agrees(m: { this: string; other: string }): boolean {
  const a = numbersIn(m.this)[0]?.value
  const b = numbersIn(m.other)[0]?.value
  if (a === undefined || b === undefined) return false
  if (a === b) return true
  const step = (n: number) => {
    let p = 1
    while (n !== 0 && n % (p * 10) === 0) p *= 10
    return p
  }
  const p = Math.max(step(a), step(b))
  return Math.round(a / p) === Math.round(b / p)
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
  if (c.verdict.label === 'partial') {
    if (namedMarks(c).length) return 'differs'
    const raw = (c.marks ?? []).filter((m) => real(m.this) && real(m.other))
    return raw.length && raw.every((m) => m.kind === 'number' && agrees(m)) ? 'same' : 'open'
  }
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
  /** From the infobox (a field, not a sentence): ranked after the sentences. */
  infobox: boolean
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
    const n = namedMarks(row.cells[l]).find((m) => m.kind === 'number' && numberText(m.other) && comparable(m))
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
  if (same.length) {
    const rest = counted.length - differs.length - missing.length
    parts.push([{ text: same.length === rest ? copy.sameInOthers(same.length) : copy.topic.sameInLangs(same) }])
  }
  if (missing.length) parts.push([{ text: copy.topic.notInLower(missing) }])
  if (changed) parts.push([{ text: copy.changedItIn(changed.l, changed.born.slice(0, 4)) }])

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
    infobox: row.section === '[infobox]' || /^[\p{L}_ ]{1,30}\d*:\s+/u.test(a.text ?? ''),
  }
}

/** Infobox rows read "losses1: 25,904 fallen"; the field name is not part of what the edition says. */
export function readable(text: string, section: string): string {
  return tidy(section === '[infobox]' ? text.replace(/^[\p{L}_ ]{1,30}\d*:\s+/u, '') : text)
}

/** Marks past this many characters would fall under the 3-line clamp of a list row (wide screen; phones pass 90). */
export const FOCUS_AT = 200
export const FOCUS_AT_PHONE = 90

/**
 * When the first mark starts past FOCUS_AT, start the text a little before it with "…" so the mark stays visible
 * under the row clamp. The full text stays on the statement page.
 */
export function focusOn(say: MarkedText, limit = FOCUS_AT): MarkedText {
  const first = say.spans[0]?.start ?? 0
  if (first <= limit) return say
  const back = Math.min(60, Math.floor((limit * 2) / 3))
  let at = say.text.lastIndexOf(' ', first - back)
  if (at < 0) at = first - back
  const cut = at + 1
  return {
    text: `…${say.text.slice(cut)}`,
    spans: say.spans.map((sp) => ({ start: sp.start - cut + 1, end: sp.end - cut + 1 })),
  }
}

/** Wiki text leftovers: HTML entities, the "<...>" cut marker, doubled quote marks, runs of spaces. */
export function tidy(text: string): string {
  return text
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#0?39;|&apos;/g, "'")
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/\s*<\s*(\.\.\.|…)\s*>\s*/g, ' ')
    .replace(/""+/g, '"')
    .replace(/''+/g, "'")
    .replace(/\s+/g, ' ')
    .trim()
}

const tidyOr = (t: string | null | undefined) => (t == null ? t : tidy(t))

/** The row with its texts tidied for reading. */
function tidyRow(row: Row): Row {
  const cells: Row['cells'] = {}
  for (const [l, c] of Object.entries(row.cells)) cells[l] = { ...c, text: tidyOr(c.text) ?? null, gloss: tidyOr(c.gloss) ?? null }
  return { ...row, cells }
}

function addDays(day: string, n: number): string {
  const d = new Date(`${day.slice(0, 10)}T00:00:00Z`)
  d.setUTCDate(d.getUTCDate() + n)
  return d.toISOString().slice(0, 10)
}

/**
 * Sentences whose differing part is marked come first (the reader sees what differs); then marked infobox fields
 * and lists with more than two marks (hard to read as a first impression); then the rest. Within each, most
 * editions differing first, then most contradicting, then the newest wording.
 */
export function rank(rows: Analysed[]): Analysed[] {
  const tier = (x: Analysed) => (!x.say.spans.length ? 0 : x.infobox || x.say.spans.length > 2 ? 1 : 2)
  return [...rows].sort(
    (x, y) =>
      tier(y) - tier(x) ||
      y.differs.length - x.differs.length ||
      y.contradicts - x.contradicts ||
      (x.newest < y.newest ? 1 : x.newest > y.newest ? -1 : 0),
  )
}

/**
 * A heading from the statement: up to the first clause boundary (comma, semicolon or dash) that leaves at
 * least 30 characters; else the whole statement when under 120; else cut at a word boundary before 100.
 * Never adds "…".
 */
export function headingOf(text: string): string {
  const t = text.trim().replace(/[.\s]+$/, '')
  for (const m of t.matchAll(/[,;]|\s[–—-]\s/g)) {
    if ((m.index ?? 0) >= 30) return t.slice(0, m.index).trim()
  }
  if (t.length < 120) return t
  const cut = t.slice(0, 100)
  const at = cut.lastIndexOf(' ')
  return (at > 0 ? cut.slice(0, at) : cut).replace(/[\s,;:–—-]+$/, '')
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

/** The words that changed between two versions, with one word of context when only words were added or cut.
 * `size` = how many words changed on the longer side; null when only punctuation, quote marks or case changed. */
export function changedWords(from: string, to: string): { from: string; to: string; size: number } | null {
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
  const size = Math.max(x.filter((w) => norm(w)).length, y.filter((w) => norm(w)).length)
  if ((!x.length || !y.length) && p > 0) {
    x = a.slice(p - 1, a.length - s)
    y = b.slice(p - 1, b.length - s)
  }
  if (!x.length || !y.length) {
    x = a.slice(p, a.length - s + 1)
    y = b.slice(p, b.length - s + 1)
  }
  return { from: cutWords(x.join(' '), 90), to: cutWords(y.join(' '), 90), size }
}

/** Shortens at a word boundary and marks the cut with "…" (a quote, not a heading). */
function cutWords(t: string, max: number): string {
  return copy.excerpt(t, max)
}

/** Strips the "/* Section *\/" prefix MediaWiki puts in edit comments. */
export function cleanComment(c: string | null): string | null {
  const s = (c ?? '').replace(/\/\*.*?\*\//g, '').replace(/\s+/g, ' ').trim()
  return s || null
}

/** Quote marks at the ends of a cut quote (the row adds its own “ ”). */
const unquote = (t: string) => t.replace(/^["“”«»„']+|["“”«»„']+(?=…?$)/g, '')

/** One edit from /api/claim/.../timeline `edits`: a sentence and the one that replaced it in one revision. */
export interface EditRaw {
  lang: string
  rev: number
  date: string | null
  time_precision: 'exact' | 'snapshot'
  from_text: string
  to_text: string
  from_gloss: string | null
  to_gloss: string | null
  comment: string | null
  /** Vector distance of the edited sentence to the statement. */
  near: number | null
  /** The edited sentence is one the judge paired with the statement. */
  paired: boolean
}

/** An edit counts as close to the statement under this distance (or when the judge paired it). */
export const NEAR = 0.41
/** Fewer changed words than this is a typo or spelling fix, not a change of what the edition says. */
export const MIN_WORDS = 3
export const MAX_CHANGES = 5

/**
 * "When it changed": edits close to the statement that change at least MIN_WORDS words, English when both
 * versions have a gloss. Readable (English) edits first, then changes of a number or a marked term, then the most changed words; at most
 * MAX_CHANGES, shown newest first.
 */
export function changesOf(edits: EditRaw[], terms: string[] = []): StatementChange[] {
  const has = (t: string, w: string) => t.toLowerCase().includes(w.toLowerCase())
  const termChange = (a: string, b: string) => terms.some((w) => w.length > 2 && has(a, w) !== has(b, w))
  const out: (StatementChange & { score: number })[] = []
  const seen = new Set<string>()
  for (const e of edits) {
    if (!isLang(e.lang) || !e.date) continue
    if (!e.paired && (e.near === null || e.near > NEAR)) continue
    const english = e.lang === 'en' || !!(e.from_gloss && e.to_gloss)
    const useGloss = e.lang !== 'en' && english
    const diff = changedWords(tidy(useGloss ? e.from_gloss! : e.from_text), tidy(useGloss ? e.to_gloss! : e.to_text))
    if (!diff || diff.size < MIN_WORDS) continue
    const key = `${e.lang}|${diff.from}|${diff.to}`
    if (seen.has(key)) continue
    seen.add(key)
    const vals = (t: string) => numbersIn(t).map((n) => n.value).sort().join(',')
    const numbers = vals(diff.from) !== vals(diff.to)
    out.push({
      date: e.date.slice(0, 10),
      lang: e.lang,
      from: unquote(diff.from),
      to: unquote(diff.to),
      comment: cleanComment(e.comment),
      url: oldid(e.lang, e.rev),
      approx: e.time_precision === 'snapshot',
      score: (english ? 2000 : 0) + (numbers || termChange(diff.from, diff.to) ? 1000 : 0) + Math.min(diff.size, 40) + (e.paired ? 0.25 : 0),
    })
  }
  return out
    .sort((x, y) => y.score - x.score || (x.date < y.date ? 1 : -1))
    .slice(0, MAX_CHANGES)
    .sort((x, y) => (x.date < y.date ? 1 : x.date > y.date ? -1 : 0))
    .map(({ score: _score, ...c }) => c)
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

/** The /api/dropped row of a removed sentence (the API also sends the last revision that had it). */
type Dropped = DroppedRowRaw & { last_rev?: number | null; last_url?: string | null }

async function findDropped(api: Client, topic: string, lang: string, h: string): Promise<Dropped | null> {
  for (let offset = 0; offset < 1000; offset += 200) {
    const r = await api.dropped({ topic, lang, min_days: 0, offset, limit: 200 })
    if (!r.ok) return null
    const hit = r.data.rows.find((x) => x.h === h)
    if (hit) return hit as Dropped
    if (r.data.rows.length < 200) return null
  }
  return null
}

/**
 * A sentence that is not a Finnish statement on this date (removed, or from another edition): the sentence
 * itself first, then how the editions that still have it tell it (through the Finnish counterpart when there
 * is one), and its removal under "When it changed".
 */
export async function otherStatement(
  api: Client,
  ctx: TopicCtx,
  lang: string,
  h: string,
  own: { text: string; gloss: string | null; url: string | null },
  dropped: Dropped | null,
) {
  own = { ...own, text: tidy(own.text) }
  const say = tidy(dropped?.gloss ?? own.gloss ?? own.text)
  const url = dropped?.last_url ?? own.url
  const first: StatementGroup = {
    langs: [lang as Lang],
    say: plain(say),
    originals: [{ lang: lang as Lang, text: own.text, url }],
    marked: [{ lang: lang as Lang, say: plain(own.text), url }],
  }
  let rest: ReturnType<typeof statementOf> | null = null
  const fi = dropped?.alive_in.find((a) => a.lang === 'fi')
  if (fi) {
    const cmp = await api.compare({ topic: ctx.topic.topicId, as_of: ctx.date ?? undefined, anchor: 'fi', h: fi.h, limit: 1 })
    const row = cmp.ok ? (cmp.data.rows.find((r) => r.cells.fi?.h === fi.h) ?? null) : null
    if (cmp.ok && row) rest = statementOf(tidyRow(row), cmp.data.anchor, new Set(Object.keys(cmp.data.editions)), { lang: 'fi', text: fi.text, gloss: null })
  }
  let groups: StatementGroup[]
  if (rest) {
    groups = rest.groups
      .map((g) => {
        const keep = g.langs.map((l, i) => [l, i] as const).filter(([l]) => l !== lang)
        return {
          langs: keep.map(([l]) => l),
          say: g.say,
          originals: g.originals.filter((o) => o.lang !== lang),
          marked: g.marked.filter((o) => o.lang !== lang),
        }
      })
      .filter((g) => g.langs.length)
  } else {
    groups = (dropped?.alive_in ?? [])
      .filter((a) => a.lang !== lang && isLang(a.lang))
      .map((a) => ({
        langs: [a.lang as Lang],
        say: plain(tidy(a.text)),
        originals: [{ lang: a.lang as Lang, text: tidy(a.text), url: a.oldid_url }],
        marked: [{ lang: a.lang as Lang, say: plain(a.text), url: a.oldid_url }],
      }))
  }
  return {
    title: say,
    groups: [first, ...groups],
    missing: (rest?.missing ?? []).filter((l) => l !== lang),
    open: (rest?.open ?? []).filter((l) => l !== lang),
  }
}

/** "When it changed" entry for the removal of a sentence. `to` is empty: the row reads "… removed it". */
export function removalOf(d: Dropped): StatementChange | null {
  if (!isLang(d.lang) || !d.died) return null
  return {
    date: d.died.slice(0, 10),
    lang: d.lang,
    from: copy.excerpt(d.gloss ?? d.text, 90),
    to: '',
    comment: cleanComment(d.died_comment),
    url: oldid(d.lang, d.died_rev),
    approx: (d as { time_precision?: string }).time_precision === 'snapshot',
  }
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
  const found = cmp.data.rows.find((r) => r.cells[lang]?.h === h) ?? null
  const row = found && tidyRow(found)
  const present = new Set(Object.keys(cmp.data.editions))
  const last = own[own.length - 1]
  const dead = !row && (!last || !!last.died)
  const dropped = dead ? await findDropped(api, ctx.topic.topicId, lang, h) : null
  const s = row
    ? statementOf(row, cmp.data.anchor, present, { lang, text: tl.data.claim.text, gloss: last?.gloss ?? null })
    : await otherStatement(api, ctx, lang, h, { text: tl.data.claim.text, gloss: last?.gloss ?? null, url: last ? oldid(lang, last.born_rev) : null }, dropped)
  const edits = changesOf(
    (tl.data as { edits?: EditRaw[] }).edits ?? [],
    row ? Object.values(row.cells).flatMap((c) => c.marks.flatMap((m) => [m.this, m.this_en ?? '', m.other === 'None' ? '' : m.other])) : [],
  )
  const removal = dropped ? removalOf(dropped) : null
  const changes = removal
    ? [removal, ...edits.slice(0, MAX_CHANGES - 1)].sort((x, y) => (x.date < y.date ? 1 : x.date > y.date ? -1 : 0))
    : edits
  const vm: WithoutCounts<StatementVM> = {
    topic: ctx.topic,
    date: ctx.date,
    title: copy.topic.oneStatementIn(ctx.topic.title, new Set(s.groups.flatMap((g) => g.langs)).size),
    groups: s.groups,
    missing: s.missing,
    open: s.open,
    changes,
    backHref: paths.differences(ctx.topic.qid),
  }
  return { ok: true, data: vm }
}
