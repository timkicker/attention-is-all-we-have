// One async function per screen. Each returns Result<VM>: under ?mock=1 from the fixture,
// otherwise from the API through the adapter in lib/adapt/. Pages call only these.
// An adapter that throws ("not built yet") comes back as a Failure with code "not_built".

import { api } from './api/client'
import * as aCheck from './adapt/check'
import * as aHood from './adapt/hood'
import * as aRemoved from './adapt/removed'
import { resolveTopic as resolveLive, type TopicCtx, type WithoutCounts } from './adapt/shared'
import * as aStart from './adapt/start'
import * as aTopic from './adapt/topic'
import { dateState } from './date.svelte'
import * as fx from './fixture'
import type {
  CheckResultVM,
  CheckVM,
  DifferencesVM,
  HoodVM,
  IngestVM,
  Lang,
  RemovedVM,
  Result,
  SearchVM,
  StartVM,
  StatementVM,
  TabCounts,
  TopicRef,
} from './model'
import { router } from './router.svelte'

const mock = () => router.mock

async function guard<T>(f: () => Promise<Result<T>>): Promise<Result<T>> {
  try {
    return await f()
  } catch (e) {
    return { ok: false, error: { status: 0, code: 'not_built', message: String(e) } }
  }
}

export async function resolveTopic(qid: string): Promise<Result<TopicRef>> {
  if (mock()) return fx.resolveTopic(qid)
  return guard(() => resolveLive(api, qid))
}

async function ctxFor(qid: string, date: string | null): Promise<Result<TopicCtx>> {
  const t = await resolveTopic(qid)
  if (!t.ok) return t
  return { ok: true, data: { topic: t.data, date, asOf: date ?? dateState.today } }
}

/** Tab counts for the topic header; never fails (unknown = null). */
export async function getCounts(qid: string, date: string | null): Promise<TabCounts> {
  if (mock()) return fx.counts(date)
  const c = await ctxFor(qid, date)
  if (!c.ok) return { differences: null, removed: null }
  const safe = (p: Promise<number | null>) => p.catch(() => null)
  const [differences, removed] = await Promise.all([
    safe(aTopic.countDifferences(api, c.data)),
    safe(aRemoved.countRemoved(api, c.data)),
  ])
  return { differences, removed }
}

/** Runs a topic adapter and adds the counts. */
async function topicPage<T extends { counts: TabCounts }>(
  qid: string,
  date: string | null,
  load: (ctx: TopicCtx) => Promise<Result<WithoutCounts<T>>>,
): Promise<Result<T>> {
  const c = await ctxFor(qid, date)
  if (!c.ok) return c
  const [r, counts] = await Promise.all([guard(() => load(c.data)), getCounts(qid, date)])
  if (!r.ok) return r
  return { ok: true, data: { ...r.data, counts } as T }
}

// ---------- Start and ingest (P1) ----------

export async function getStart(): Promise<Result<StartVM>> {
  if (mock()) return fx.start()
  return guard(() => aStart.loadStart(api))
}

export async function search(q: string): Promise<Result<SearchVM>> {
  if (mock()) return fx.search(q)
  return guard(() => aStart.loadSearch(api, q))
}

export async function startIngest(qid: string, since?: string): Promise<Result<IngestVM>> {
  if (mock()) return fx.ingest(qid, since ? 2 : Number(router.query.get('step') ?? 1))
  return guard(() => aStart.startIngest(api, qid, since))
}

/** Under ?mock=1, ?step=1 is wireframe 03, ?step=2 is wireframe 04, ?step=3 has Russian rate-limited. */
export async function getIngest(qid: string): Promise<Result<IngestVM>> {
  if (mock()) return fx.ingest(qid, Number(router.query.get('step') ?? 1))
  return guard(() => aStart.loadIngest(api, qid))
}

// ---------- Topic tabs (P2, P3) ----------

export async function getDifferences(
  qid: string,
  date: string | null,
  opts: { q?: string; offset?: number } = {},
): Promise<Result<DifferencesVM>> {
  const o = { q: opts.q ?? '', offset: opts.offset ?? 0 }
  if (mock()) return fx.differences(qid, date, o)
  return topicPage<DifferencesVM>(qid, date, (ctx) => aTopic.loadDifferences(api, ctx, o))
}

export async function getStatement(
  qid: string,
  date: string | null,
  lang: string,
  pageId: string,
  h: string,
): Promise<Result<StatementVM>> {
  if (mock()) return fx.statement(qid, date, lang, pageId, h)
  return topicPage<StatementVM>(qid, date, (ctx) => aTopic.loadStatement(api, ctx, lang, pageId, h))
}

export async function getRemoved(
  qid: string,
  date: string | null,
  opts: { q?: string; offset?: number; edition?: Lang | null } = {},
): Promise<Result<RemovedVM>> {
  const o = { q: opts.q ?? '', offset: opts.offset ?? 0, edition: opts.edition ?? null }
  if (mock()) return fx.removed(qid, date, o)
  return topicPage<RemovedVM>(qid, date, (ctx) => aRemoved.loadRemoved(api, ctx, o))
}

export async function getCheckRecorded(qid: string, date: string | null): Promise<Result<CheckVM>> {
  if (mock()) return fx.check(qid, date)
  return topicPage<CheckVM>(qid, date, (ctx) => aCheck.loadCheck(api, ctx))
}

export async function runCheck(qid: string, date: string | null, text: string): Promise<Result<{ runId: string }>> {
  if (mock()) return fx.runCheck(text)
  const c = await ctxFor(qid, date)
  if (!c.ok) return c
  return guard(() => aCheck.runCheck(api, c.data, text))
}

export async function getCheckRun(qid: string, date: string | null, runId: string): Promise<Result<CheckResultVM>> {
  if (mock()) return fx.checkRun(qid, date, runId)
  return topicPage<CheckResultVM>(qid, date, (ctx) => aCheck.loadCheckRun(api, ctx, runId))
}

// ---------- Under the hood (P4) ----------

export async function getHood(fromQid: string | null): Promise<Result<HoodVM>> {
  if (mock()) return fx.hood(fromQid)
  let from: TopicRef | null = null
  if (fromQid) {
    const t = await resolveTopic(fromQid)
    if (t.ok) from = t.data
  }
  return guard(() => aHood.loadHood(api, from))
}
