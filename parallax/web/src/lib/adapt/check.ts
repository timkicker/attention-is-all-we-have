// Check an AI answer: raw API -> view model. Owner: P3.
// Per statement the API labels every edition: says, stopped_saying, contradicts or not_found.
// The row line follows from those labels, most cautious first:
//   some edition contradicts it            -> Disputed, <those editions> say otherwise
//   else some edition stopped saying it    -> Disputed, in <says> of <all>, <edition> removed it in <year>
//   else some edition says it              -> Backed by <says> of <all> editions
//                                             (Likely backed by ..., when only the similarity guess matched it)
//   else                                   -> In no edition
import type { api as Api } from '../api/client'
import type { CheckRecordedRes, CheckRes, EvidenceRaw } from '../api/types'
import { backedBy, DISPUTED, disputedOtherwise, excerpt, IN_NO_EDITION, likelyBackedBy } from '../copy'
import { fmtYear } from '../format'
import { LANGS, type CheckResultVM, type CheckRow, type CheckVerdict, type CheckVM, type Result } from '../model'
import { paths } from '../router.svelte'
import * as checkCopy from '../copy/check'
import type { TopicCtx, WithoutCounts } from './shared'
import { EXAMPLE_QID } from './start'

type Client = typeof Api
type Claim = CheckRes['claims'][number]
type Recorded = CheckRecordedRes['runs'][number]

/** The offline judge that only compares shared names and numbers (contract/engine.py FAKE_GUESS_MODEL). */
export const GUESS_MODEL = 'fake-judge-similarity'

/** How many recorded answers the Check page offers. */
export const RECORDED_MAX = 3

const order = (lang: string) => {
  const i = (LANGS as readonly string[]).indexOf(lang)
  return i < 0 ? LANGS.length : i
}
const byEdition = (a: string, b: string) => order(a) - order(b)

/** "gemini-3.8-flash" -> "Gemini"; a model written as words stays as it is, first letter up. */
export function modelName(model: string | null): string | null {
  const m = model?.trim()
  if (!m) return null
  const name = /\s/.test(m) ? m : m.split(/[-_/ ]/)[0]
  return name.charAt(0).toUpperCase() + name.slice(1)
}

/** "Who fired the shots at Mainila in November 1939?" -> "who fired the shots at Mainila in November 1939". */
function questionPart(q: string | null): string | null {
  const s = q?.trim().replace(/[?.!\s]+$/, '')
  if (!s) return null
  return s.charAt(0).toLowerCase() + s.slice(1)
}

/** Longest question shown in a recorded-answer label; a longer one is cut at the last word boundary before it. */
export const QUESTION_MAX = 80

function capped(q: string): string {
  if (q.length <= QUESTION_MAX) return q
  const cut = q.slice(0, QUESTION_MAX + 1)
  const at = cut.lastIndexOf(' ')
  return (at > 0 ? cut.slice(0, at) : q.slice(0, QUESTION_MAX)).replace(/[\s,;:]+$/, '')
}

/** The recorded answer's label, built only from its stored data: "<model> on <question>". */
export function recordedLabel(r: { answer_model: string | null; question: string | null }): string | null {
  const m = modelName(r.answer_model)
  const short = r.question ? checkCopy.QUESTION_TOPICS.find(([re]) => re.test(r.question ?? ''))?.[1] : undefined
  const part = questionPart(r.question)
  const q = short ?? (part ? capped(part) : null)
  if (m && q) return `${m} on ${q}`
  return m ?? (q ? q.charAt(0).toUpperCase() + q.slice(1) : null)
}

/** Questions the Check page offers first: the Mainila shots, then the losses. */
const FIRST_QUESTIONS = [/mainila/i, /died|killed|losses|lost/i]
const rank = (q: string | null) => {
  const i = FIRST_QUESTIONS.findIndex((rx) => rx.test(q ?? ''))
  return i < 0 ? FIRST_QUESTIONS.length : i
}

/** Up to max recorded answers: Mainila and losses questions first, one per question before any repeat. */
export function pickRecorded(runs: Recorded[], max = RECORDED_MAX): Recorded[] {
  const seen = new Set<string>()
  const first: Recorded[] = []
  const rest: Recorded[] = []
  // The fake engine's example answer (record_checks --fixture) only stands in until real answers are recorded.
  const fixture = (r: Recorded) => (/test fixture/i.test(r.answer_model ?? '') ? 1 : 0)
  const sorted = runs
    .map((r, i) => ({ r, i }))
    .sort((a, b) => fixture(a.r) - fixture(b.r) || rank(a.r.question) - rank(b.r.question) || a.i - b.i)
  for (const { r } of sorted) {
    const k = r.question ?? r.run_id
    if (seen.has(k)) rest.push(r)
    else {
      seen.add(k)
      first.push(r)
    }
  }
  return [...first, ...rest].slice(0, max)
}

function evidenceHref(qid: string, e: EvidenceRaw | undefined): string | null {
  return e ? paths.statement(qid, e.lang, e.page_id, e.h) : null
}

/** One statement of the answer -> its row. */
export function toCheckRow(qid: string, c: Claim): CheckRow {
  const per = Object.entries(c.per_lang).sort(([a], [b]) => byEdition(a, b))
  const all = per.length
  const withLabel = (l: string) => per.filter(([, v]) => v.label === l)
  const says = withLabel('says')
  const stopped = withLabel('stopped_saying')
  const contradicts = withLabel('contradicts')
  // Evidence for the statement page: an edition that says it, Finnish first; else what disputes it.
  const ev =
    says.find(([l]) => l === 'fi')?.[1].evidence[0] ??
    says[0]?.[1].evidence[0] ??
    stopped[0]?.[1].evidence[0] ??
    contradicts[0]?.[1].evidence[0]

  let verdict: CheckVerdict
  let head: readonly string[]
  if (contradicts.length) {
    verdict = 'disputed'
    head = disputedOtherwise(contradicts.map(([l]) => l))
  } else if (stopped.length && says.length && says.length * 2 <= all) {
    // A real removal (rewordings are filtered out by the API) and at most half the editions still say it.
    verdict = 'disputed'
    const died = stopped.map(([, v]) => v.evidence[0]?.died ?? '').sort().at(-1)
    const year = died ? fmtYear(died) : null
    head =
      stopped.length > 2 || !year
        ? checkCopy.disputedRemovedIn(says.length, all, stopped.length)
        : checkCopy.disputedRemovedBy(says.length, all, stopped.map(([l]) => l), year)
  } else if (says.length) {
    verdict = 'backed'
    const guessed = says.every(([, v]) => v.evidence.every((e) => e.verdict?.model === GUESS_MODEL))
    head = [guessed ? likelyBackedBy(says.length, all) : backedBy(says.length, all)]
  } else {
    verdict = 'none'
    head = [IN_NO_EDITION]
  }
  return { id: String(c.idx), verdict, head, say: c.text, href: verdict === 'none' ? null : evidenceHref(qid, ev) }
}

/** /api/check/recorded -> recorded answers (labels come from the data). They answer Winter War questions, so only
 *  the Winter War offers them: on another article "Gemini on Mainila" would open a Winter War answer under its title. */
export async function loadCheck(api: Client, ctx: TopicCtx): Promise<Result<WithoutCounts<CheckVM>>> {
  if (ctx.topic.qid !== EXAMPLE_QID) return { ok: true, data: { topic: ctx.topic, date: ctx.date, recorded: [] } }
  const r = await api.checkRecorded()
  if (!r.ok) return r
  const recorded = pickRecorded(r.data.runs).flatMap((run) => {
    const label = recordedLabel(run)
    return label ? [{ runId: run.run_id, label, href: paths.checkRun(ctx.topic.qid, run.run_id) }] : []
  })
  return { ok: true, data: { topic: ctx.topic, date: ctx.date, recorded } }
}

/** POST /api/check -> the new run id. */
export async function runCheck(api: Client, ctx: TopicCtx, text: string): Promise<Result<{ runId: string }>> {
  // Evidence only from this article: other loaded articles may hold near sentences too.
  const r = await api.check({ text, topic: ctx.topic.topicId, ...(ctx.date ? { as_of: ctx.date } : {}) })
  if (!r.ok) return r
  return { ok: true, data: { runId: r.data.run_id } }
}

/** GET /api/check/:runId (on ctx.date when one is chosen). */
export async function loadCheckRun(
  api: Client,
  ctx: TopicCtx,
  runId: string,
): Promise<Result<WithoutCounts<CheckResultVM>>> {
  const r = await api.checkRun(runId, ctx.date ?? undefined)
  if (!r.ok) return r
  return { ok: true, data: toResult(ctx, r.data) }
}

export function toResult(ctx: TopicCtx, d: CheckRes): WithoutCounts<CheckResultVM> {
  // As in wireframe 10: statements in no edition first, then disputed, then backed (most editions first).
  const weight = { disputed: 0, none: 1, backed: 2 } as const
  const says = (c: Claim) => Object.values(c.per_lang).filter((v) => v.label === 'says').length
  const rows = d.claims
    .map((c, i) => ({ row: toCheckRow(ctx.topic.qid, c), n: says(c), i }))
    .sort((a, b) => weight[a.row.verdict] - weight[b.row.verdict] || (a.row.verdict === 'backed' ? b.n - a.n : 0) || a.i - b.i)
    .map((x) => x.row)
  const mostBacked = d.claims.every((c) => {
    const per = Object.values(c.per_lang)
    const says = per.filter((v) => v.label === 'says').length
    const backed = !per.some((v) => v.label === 'contradicts' || v.label === 'stopped_saying') && says > 0
    return !backed || says * 2 > per.length
  })
  const count = (v: CheckVerdict) => rows.filter((x) => x.verdict === v).length
  // Older API versions do not return the answer; the statements then stand in for it.
  const answer = d.text ?? d.claims.map((c) => c.text).join(' ')
  return {
    topic: ctx.topic,
    date: ctx.date,
    runId: d.run_id,
    label: d.source === 'recorded' ? recordedLabel({ answer_model: d.answer_model, question: d.question ?? null }) : null,
    recordedOn: d.source === 'recorded' ? d.answer_date : null,
    answer,
    excerpt: excerpt(answer),
    summary: { total: rows.length, none: count('none'), disputed: count('disputed'), backed: count('backed') },
    rows,
    mostBacked,
    againHref: paths.check(ctx.topic.qid),
  }
}
