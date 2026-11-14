// Start page, search and ingest: raw API -> view model. Owner: P1. Stubs until P1 builds them.
import type { api as Api } from '../api/client'
import type { IngestVM, Result, SearchVM, StartVM } from '../model'

type Client = typeof Api

/** Prepared topics (from /api/topics) and the example block. */
export async function loadStart(_api: Client): Promise<Result<StartVM>> {
  throw new Error('not built yet')
}
/** GET /api/search?q. */
export async function loadSearch(_api: Client, _q: string): Promise<Result<SearchVM>> {
  throw new Error('not built yet')
}
/** POST /api/ingest. */
export async function startIngest(_api: Client, _qid: string, _since?: string): Promise<Result<IngestVM>> {
  throw new Error('not built yet')
}
/** GET /api/ingest/:qid. */
export async function loadIngest(_api: Client, _qid: string): Promise<Result<IngestVM>> {
  throw new Error('not built yet')
}
