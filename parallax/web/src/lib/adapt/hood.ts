// Under the hood: raw API -> view model. Owner: P4.
// Every number comes from the API: versions from /api/topics, recall and model agreement from the stat
// judge_eval (left out when it was never measured), the embedding rate from embed_rate, the query and its
// milliseconds from the SQL log of the Differences list (/api/sql/compare, else one /api/compare call).
import type { api as Api } from '../api/client'
import type { SqlStatement, TopicsRes } from '../api/types'
import type { HoodVM, Result, TopicRef } from '../model'

type Client = typeof Api

/** One bound parameter of a logged statement (a list only by its length). */
type Param = NonNullable<SqlStatement['params']>[string]

const VEC = /VEC_DISTANCE/i

/** The statement that finds the closest statements: the vector statement that returned the most rows. */
export function pickQuery(statements: SqlStatement[]): SqlStatement | null {
  let best: SqlStatement | null = null
  for (const s of statements) if (VEC.test(s.text) && (!best || s.rows > best.rows)) best = s
  return best
}

function literal(v: Param): string {
  if (v === null) return 'NULL'
  if (typeof v === 'number') return String(v)
  if (typeof v === 'object') return `(/* ${v.count} values */)`
  return `'${v.replace(/'/g, "''")}'`
}

const KEYWORD_BREAK = / (?=ORDER BY |IGNORE INDEX|AND |ON )/g

/** Where to break rest so the first part fits max: after a ", " outside parentheses, else before a keyword. */
function breakAt(rest: string, max: number, minCut: number): { at: number; skip: number } | null {
  let depth = 0
  let comma = -1
  for (let i = 0; i < Math.min(rest.length, max); i++) {
    const ch = rest[i]
    if (ch === '(') depth++
    else if (ch === ')') depth--
    else if (ch === ',' && rest[i + 1] === ' ' && depth === 0 && i > minCut) comma = i
  }
  if (comma > 0) return { at: comma + 1, skip: comma + 2 }
  let kw = -1
  for (const m of rest.matchAll(KEYWORD_BREAK)) if (m.index > minCut && m.index < max) kw = m.index
  return kw > 0 ? { at: kw, skip: kw + 1 } : null
}

/** Breaks a line longer than max outside parentheses, continuing two spaces deeper. The words stay the same. */
export function wrapLine(line: string, max = 72): string[] {
  if (line.length <= max) return [line]
  const indent = line.length - line.trimStart().length
  const pad = ' '.repeat(indent + 2)
  const out: string[] = []
  let rest = line
  while (rest.length > max) {
    const b = breakAt(rest, max, pad.length)
    if (!b) break
    out.push(rest.slice(0, b.at))
    rest = pad + rest.slice(b.skip).trimStart()
  }
  out.push(rest)
  return out
}

/** The statement as it ran: parameters written in, common indent removed, long lines wrapped at commas. */
export function formatSql(s: SqlStatement): string {
  const params = s.params ?? {}
  const text = s.text.replace(/%\((\w+)\)s/g, (m, name: string) => (name in params ? literal(params[name]) : m))
  const lines = text
    .replace(/\s+$/, '')
    .split('\n')
    .map((l) => l.replace(/\s+$/, ''))
  const indents = lines.filter((l) => l.trim()).map((l) => l.length - l.trimStart().length)
  const cut = indents.length ? Math.min(...indents) : 0
  return `${lines.flatMap((l) => wrapLine(l.slice(cut))).join('\n')};`
}

const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null)
const obj = (v: unknown): Record<string, unknown> | null =>
  v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : null

/** Numbers measured offline and stored in table stat; null where a stat is missing. */
export function fromStats(
  stats: Record<string, unknown> | null,
): Pick<HoodVM, 'top1' | 'top5' | 'embedRate' | 'embedGpu' | 'judgeAccuracy' | 'judgeN'> {
  const ev = obj(stats?.judge_eval)
  const align = obj(ev?.alignment)
  const embed = obj(stats?.embed_rate)
  const gpu = embed?.gpu
  return {
    top1: num(align?.['R@1']),
    top5: num(align?.['R@5']),
    embedRate: num(embed?.per_s),
    embedGpu: typeof gpu === 'string' && gpu.trim() ? gpu.trim() : null,
    judgeAccuracy: num(ev?.accuracy),
    judgeN: num(ev?.n),
  }
}

/** Versions stored = the revisions stored for every edition of the topic. */
export function versionsOf(topics: TopicsRes | null, topicId: string): number | null {
  const t = topics?.topics.find((x) => x.topic_id === topicId)
  if (!t || !t.editions.length) return null
  let n = 0
  for (const e of t.editions) {
    if (typeof e.revisions !== 'number') return null
    n += e.revisions
  }
  return n
}

export async function loadHood(api: Client, from: TopicRef | null): Promise<Result<HoodVM>> {
  const [topics, stats, logged] = await Promise.all([api.topics(), api.stats(), api.sqlPanel('compare')])
  const topicsRes = topics.ok ? topics.data : null
  let statements: SqlStatement[] = logged.ok ? logged.data.statements : []
  const loggedTopic = pickQuery(statements)?.params?.topic
  const topicId =
    from?.topicId ?? (typeof loggedTopic === 'string' ? loggedTopic : null) ?? topicsRes?.topics[0]?.topic_id ?? null
  if (!pickQuery(statements) && topicId) {
    // No Differences list ran since the API started: run it once to get its statements.
    const c = await api.compare({ topic: topicId })
    if (c.ok) statements = c.data.sql
    else return c
  }
  const q = pickQuery(statements)
  if (!q) return { ok: false, error: { status: 0, code: 'no_query', message: 'No Differences list query was logged.' } }
  const t = topicsRes?.topics.find((x) => x.topic_id === topicId)
  return {
    ok: true,
    data: {
      from,
      topicTitle: from?.title ?? t?.label_en ?? topicId ?? '',
      versions: topicId ? versionsOf(topicsRes, topicId) : null,
      ...fromStats(stats.ok ? stats.data.stats : null),
      queryMs: q.ms,
      sql: formatSql(q),
    },
  }
}
