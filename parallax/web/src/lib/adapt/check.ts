// Check an AI answer: raw API -> view model. Owner: P3.
// Per statement the API labels every edition: says, stopped_saying, contradicts or not_found.
// The row line follows from those labels, most cautious first:
//   some edition contradicts it            -> Disputed · <those editions> say otherwise
//   else some edition stopped saying it    -> Disputed · in <says> of <all>, <edition> removed it in <year>
//   else some edition says it              -> Backed by <says> of <all> editions
//   else                                   -> In no edition
import type { api as Api } from '../api/client'
import type { CheckRecordedRes, CheckRes, EvidenceRaw } from '../api/types'
import { backedBy, DISPUTED, disputedOtherwise, disputedRemoved, excerpt, IN_NO_EDITION } from '../copy'
import { fmtYear } from '../format'
import { LANGS, type CheckResultVM, type CheckRow, type CheckVerdict, type CheckVM, type Result } from '../model'
import { paths } from '../router.svelte'
import type { TopicCtx, WithoutCounts } from './shared'

type Client = typeof Api
type Claim = CheckRes['claims'][number]
type Recorded = CheckRecordedRes['runs'][number]

/**
 * The result plus one fact the shared view model lacks: whether every backed statement has most editions
 * behind it. false makes the summary say "backed by at least one edition" (copy.check.summary).
 */
export type CheckResultView = CheckResultVM & { mostBacked?: boolean }

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

/** The recorded answer's label, built only from its stored data: "<model> on <question>". */
export function recordedLabel(r: { answer_model: string | null; question: string | null }): string | null {
  const m = modelName(r.answer_model)
  const q = questionPart(r.question)
  if (m && q) return `${m} on ${q}`
  return m ?? (q ? q.charAt(0).toUpperCase() + q.slice(1) : null)
}

/** Up to max recorded answers, one per question first, so the links show different questions. */
export function pickRecorded(runs: Recorded[], max = RECORDED_MAX): Recorded[] {
  const seen = new Set<string>()
  const first: Recorded[] = []
  const rest: Recorded[] = []
  for (const r of runs) {
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
  let head: string
  if (contradicts.length) {
    verdict = 'disputed'
    head = disputedOtherwise(contradicts.map(([l]) => l))
  } else if (stopped.length) {
    verdict = 'disputed'
    // The edition that removed it last; its evidence is the sentence life that ended.
    const [lang, v] = [...stopped].sort(([, a], [, b]) => (b.evidence[0]?.died ?? '').localeCompare(a.evidence[0]?.died ?? ''))[0]
    const died = v.evidence[0]?.died
    head = died ? disputedRemoved(says.length, all, lang, fmtYear(died)) : DISPUTED
  } else if (says.length) {
    verdict = 'backed'
    head = backedBy(says.length, all)
  } else {
    verdict = 'none'
    head = IN_NO_EDITION
  }
  return { id: String(c.idx), verdict, head, say: c.text, href: verdict === 'none' ? null : evidenceHref(qid, ev) }
}

/** /api/check/recorded -> recorded answers (labels come from the data). */
export async function loadCheck(api: Client, ctx: TopicCtx): Promise<Result<WithoutCounts<CheckVM>>> {
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
  const r = await api.check({ text, ...(ctx.date ? { as_of: ctx.date } : {}) })
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
  return { ok: true, data: toResult(ctx, r.data as CheckRes & { text?: string; question?: string | null }) }
}

export function toResult(ctx: TopicCtx, d: CheckRes & { text?: string; question?: string | null }): WithoutCounts<CheckResultView> {
  const rows = d.claims.map((c) => toCheckRow(ctx.topic.qid, c))
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
    againHref: paths.check(ctx.topic.qid),
    mostBacked,
  }
}
