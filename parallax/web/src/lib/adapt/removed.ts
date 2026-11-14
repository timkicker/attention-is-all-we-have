// Removed tab: raw API -> view model. Owner: P3. Stubs until P3 builds them.
import type { api as Api } from '../api/client'
import type { Lang, RemovedVM, Result } from '../model'
import type { TopicCtx, WithoutCounts } from './shared'

type Client = typeof Api

/** /api/dropped?topic&lang -> rows. */
export async function loadRemoved(
  _api: Client,
  _ctx: TopicCtx,
  _opts: { q: string; offset: number; edition: Lang | null },
): Promise<Result<WithoutCounts<RemovedVM>>> {
  throw new Error('not built yet')
}
/** The Removed tab count on ctx.asOf. */
export async function countRemoved(_api: Client, _ctx: TopicCtx): Promise<number | null> {
  return null
}
