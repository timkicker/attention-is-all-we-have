// Check an AI answer: raw API -> view model. Owner: P3. Stubs until P3 builds them.
import type { api as Api } from '../api/client'
import type { CheckResultVM, CheckVM, Result } from '../model'
import type { TopicCtx, WithoutCounts } from './shared'

type Client = typeof Api

/** /api/check/recorded -> recorded answers (labels come from the data). */
export async function loadCheck(_api: Client, _ctx: TopicCtx): Promise<Result<WithoutCounts<CheckVM>>> {
  throw new Error('not built yet')
}
/** POST /api/check -> the new run id. */
export async function runCheck(_api: Client, _ctx: TopicCtx, _text: string): Promise<Result<{ runId: string }>> {
  throw new Error('not built yet')
}
/** GET /api/check/:runId. */
export async function loadCheckRun(
  _api: Client,
  _ctx: TopicCtx,
  _runId: string,
): Promise<Result<WithoutCounts<CheckResultVM>>> {
  throw new Error('not built yet')
}
