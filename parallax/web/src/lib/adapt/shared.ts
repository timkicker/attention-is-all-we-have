// Shared adapter context and topic resolution. Owner: S (shell).
import type { api as Api } from '../api/client'
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

/** The newest stored revision over a topic's editions, YYYY-MM-DD; null when the API does not say. */
export function latestOf(editions: { last_ts?: string | null }[]): string | null {
  const days = editions.map((e) => e.last_ts?.slice(0, 10)).filter((d): d is string => !!d)
  return days.length ? days.sort().at(-1)! : null
}

/** qid (Wikidata id) -> TopicRef through /api/topics. Cached; call forgetTopics() after an ingest. */
export async function resolveTopic(api: typeof Api, qid: string): Promise<Result<TopicRef>> {
  topicsCache ??= api.topics().then((r) =>
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
  const t = r.data.find((x) => x.qid === qid)
  return t ? { ok: true, data: t } : { ok: false, error: { status: 404, code: 'topic_not_found', message: qid } }
}

export function forgetTopics(): void {
  topicsCache = null
}
