// Under the hood: raw API -> view model. Owner: P4. Stub until P4 builds it.
import type { api as Api } from '../api/client'
import type { HoodVM, Result, TopicRef } from '../model'

type Client = typeof Api

/** /api/health, /api/stats, /api/sql/compare. from = the topic the reader came from. */
export async function loadHood(_api: Client, _from: TopicRef | null): Promise<Result<HoodVM>> {
  throw new Error('not built yet')
}
