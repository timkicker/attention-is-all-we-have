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

/** The statement that reads the closest statements per edition (rank column rnk): from table align when it holds
 *  the day, else the live vector search. Falls back to any vector statement. Most rows wins. */
export function pickQuery(statements: SqlStatement[]): SqlStatement | null {
  const best = (xs: SqlStatement[]) => xs.reduce<SqlStatement | null>((b, s) => (!b || s.rows > b.rows ? s : b), null)
  return best(statements.filter((s) => /\brnk\b/.test(s.text))) ?? best(statements.filter((s) => VEC.test(s.text)))
}

/** 'stored' when the statement reads the stored matches (table align), else 'vector'. */
export function queryKind(s: SqlStatement): 'stored' | 'vector' {
  return /\bFROM align\b/i.test(s.text) && !VEC.test(s.text) ? 'stored' : 'vector'
}

/** "NVIDIA A100-SXM4-80GB on Verda, bge-m3 fp16" -> "A100 GPU, bge-m3"; anything else as it is. */
export function shortGpu(gpu: string): string {
  const card = gpu.match(/\b([A-Z]\d{2,3})(?=[-\s]|$)/)?.[1]
  const model = gpu.split(',')[1]?.trim().split(/\s+/)[0]
  return card && model ? `${card} GPU, ${model}` : gpu
}

function literal(v: Param): string {
  if (v === null) return 'NULL'
  if (typeof v === 'number') return String(v)
  if (typeof v === 'object') return `(/* ${v.count} ${v.count === 1 ? 'value' : 'values'} */)`
  return `'${v.replace(/'/g, "''")}'`
}

// Clause keywords that start a new line. ON, AND, OR and the table options go one step deeper.
const CLAUSES = ['UNION ALL', 'UNION', 'SELECT', 'FROM', 'LEFT JOIN', 'JOIN', 'WHERE', 'GROUP BY', 'HAVING', 'ORDER BY', 'LIMIT', 'OFFSET']
const DEEPER = ['ON', 'AND', 'OR', 'FOR SYSTEM_TIME', 'IGNORE INDEX']
const KEYWORD = new RegExp(`^(${[...CLAUSES, ...DEEPER].map((k) => k.replace(' ', ' +')).join('|')})\\b`, 'i')
/** A SELECT list line breaks after a comma once it is this long. */
const LIST_WIDTH = 36

/** Re-indents one SQL statement for reading: one clause per line, two spaces per subquery, runs of spaces
 *  collapsed. Quoted text and comments stay as they are; parentheses of functions are never split. */
export function prettySql(sql: string): string {
  const lines: string[] = []
  const stack: { sub: boolean; clause: string }[] = []
  let level = 0
  let clause = ''
  let cur = ''
  let deeper = false
  const flush = () => {
    const t = cur.trim()
    if (t) lines.push('  '.repeat(level + (deeper ? 1 : 0)) + t)
    cur = ''
  }
  const inFunc = () => stack.length > 0 && !stack[stack.length - 1].sub
  let i = 0
  while (i < sql.length) {
    const ch = sql[i]
    const rest = sql.slice(i)
    if (ch === "'" || ch === '`' || ch === '"') {
      let j = i + 1
      while (j < sql.length && sql[j] !== ch) j++
      cur += sql.slice(i, j + 1)
      i = j + 1
      continue
    }
    if (rest.startsWith('/*')) {
      const j = sql.indexOf('*/', i + 2)
      const stop = j < 0 ? sql.length : j + 2
      cur += sql.slice(i, stop)
      i = stop
      continue
    }
    if (/\s/.test(ch)) {
      if (cur && !cur.endsWith(' ') && !cur.endsWith('(')) cur += ' '
      i++
      continue
    }
    const atWord = i === 0 || /[\s(),]/.test(sql[i - 1])
    const kw = atWord && !inFunc() ? rest.match(KEYWORD) : null
    if (kw) {
      const word = kw[1].toUpperCase().replace(/ +/g, ' ')
      flush()
      deeper = DEEPER.includes(word)
      if (!deeper) clause = word
      cur = word
      i += kw[1].length
      continue
    }
    if (ch === '(') {
      const sub = /^\(\s*SELECT\b/i.test(rest)
      stack.push({ sub, clause })
      cur += '('
      i++
      if (sub) {
        flush()
        level++
        deeper = false
      }
      continue
    }
    if (ch === ')') {
      const top = stack.pop()
      if (top?.sub) {
        flush()
        level = Math.max(0, level - 1)
        clause = top.clause
        deeper = false
        cur = ')'
      } else {
        if (cur.endsWith(' ')) cur = cur.slice(0, -1)
        cur += ')'
      }
      i++
      continue
    }
    if (ch === ',' && clause === 'SELECT' && !inFunc()) {
      cur += ','
      i++
      if (cur.trim().length >= LIST_WIDTH) {
        flush()
        deeper = true
      }
      continue
    }
    cur += ch
    i++
  }
  flush()
  return lines.join('\n')
}

/** The statement as it ran: parameters written in, then re-indented by prettySql. */
export function formatSql(s: SqlStatement): string {
  const params = s.params ?? {}
  const text = s.text.replace(/%\((\w+)\)s/g, (m, name: string) => (name in params ? literal(params[name]) : m))
  return `${prettySql(text.trim().replace(/;$/, ''))};`
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
    embedGpu: typeof gpu === 'string' && gpu.trim() ? shortGpu(gpu.trim()) : null,
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

/** HoodVM plus what the shown statement does (model.ts has no field for it yet). */
export type HoodLiveVM = HoodVM & { queryKind: 'stored' | 'vector' }

export async function loadHood(api: Client, from: TopicRef | null): Promise<Result<HoodLiveVM>> {
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
      queryKind: queryKind(q),
      sql: formatSql(q),
    },
  }
}
