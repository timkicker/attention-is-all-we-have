// Shared adapter context and topic resolution. Owner: S (shell).
import type { api as Api } from '../api/client'
import type { TopicsRes } from '../api/types'
import type { Result, TopicRef } from '../model'

/** What every topic adapter gets. date = chosen date or null (today); asOf = the date to send to the API. */
export interface TopicCtx {
  topic: TopicRef
  date: string | null
  asOf: string
}

/** Adapters return the VM without tab counts; data.ts adds them. */
export type WithoutCounts<T> = Omit<T, 'counts'>

let topicsCache: Promise<Result<TopicRef[]>> | null = null
let topicsRaw: Promise<Result<TopicsRes>> | null = null

/** /api/topics once per page load (until forgetTopics): the topic list and the edition start dates share it. */
export async function topicList(api: typeof Api): Promise<Result<TopicsRes>> {
  topicsRaw ??= api.topics()
  const r = await topicsRaw
  if (!r.ok) topicsRaw = null
  return r
}

/** The newest stored revision over a topic's editions, YYYY-MM-DD; null when the API does not say. */
export function latestOf(editions: { last_ts?: string | null }[]): string | null {
  const days = editions.map((e) => e.last_ts?.slice(0, 10)).filter((d): d is string => !!d)
  return days.length ? days.sort().at(-1)! : null
}

/** qid (Wikidata id) -> TopicRef through /api/topics. Cached; call forgetTopics() after an ingest. */
export async function resolveTopic(api: typeof Api, qid: string): Promise<Result<TopicRef>> {
  topicsCache ??= topicList(api).then((r) =>
    r.ok
      ? {
          ok: true as const,
          data: r.data.topics.map((t) => ({ qid: t.wikidata_id, topicId: t.topic_id, title: t.label_en, latest: latestOf(t.editions) })),
        }
      : r,
  )
  const r = await topicsCache
  if (!r.ok) {
    topicsCache = null
    return r
  }
  // a link may name the topic by its id (/t/winterwar) instead of its Wikidata id
  const t = r.data.find((x) => x.qid === qid) ?? r.data.find((x) => x.topicId === qid)
  return t ? { ok: true, data: t } : { ok: false, error: { status: 404, code: 'topic_not_found', message: qid } }
}

/** Caches of the topic adapters (Differences, Removed) that hold data an ingest can change. */
const forgetters: (() => void)[] = []

/** Register a cache to drop together with the topic list (adapters call this once at module load). */
export function onForget(f: () => void): void {
  forgetters.push(f)
}

/** Drop the topic list and every adapter cache: an ingest stored another edition or finished. */
export function forgetTopics(): void {
  topicsCache = null
  topicsRaw = null
  for (const f of forgetters) f()
}
