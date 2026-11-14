// Differences tab and one statement: raw API -> view model. Owner: P2. Stubs until P2 builds them.
import type { api as Api } from '../api/client'
import type { DifferencesVM, Result, StatementVM } from '../model'
import type { TopicCtx, WithoutCounts } from './shared'

type Client = typeof Api

/** /api/compare (as_of = ctx.asOf) -> rows that differ. */
export async function loadDifferences(
  _api: Client,
  _ctx: TopicCtx,
  _opts: { q: string; offset: number },
): Promise<Result<WithoutCounts<DifferencesVM>>> {
  throw new Error('not built yet')
}
/** How many statements differ on ctx.asOf (the Differences tab count). */
export async function countDifferences(_api: Client, _ctx: TopicCtx): Promise<number | null> {
  return null
}
/** /api/claim/:lang/:pageId/:h/timeline (+ compare for the other editions). */
export async function loadStatement(
  _api: Client,
  _ctx: TopicCtx,
  _lang: string,
  _pageId: string,
  _h: string,
): Promise<Result<WithoutCounts<StatementVM>>> {
  throw new Error('not built yet')
}
