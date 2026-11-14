// Typed fetch for the Parallax API. Types come from contract/openapi.yaml (npm run types).
import { shallowRef } from 'vue'
import type { components } from './schema'

export type S = components['schemas']
export type Health = S['Health']
export type Topics = S['Topics']
export type Topic = Topics['topics'][number]
export type Compare = S['Compare']
export type CompareRow = Compare['rows'][number]
export type Cell = S['Cell']
export type Timeline = S['Timeline']
export type Life = S['Life']
export type Statement = S['Statement']
export type Dropped = S['Dropped']
export type Check = S['Check'] & { question?: string | null; as_of?: string | null }
export type CheckClaim = Check['claims'][number]
export type Evidence = S['Evidence']
export type CheckRecorded = S['CheckRecorded']
export type Stats = S['Stats']
export type Ask = S['Ask']
export type Quote = Ask['quotes'][string][number]
export type Sources = S['Sources'] & { as_of?: string }
export type SourceEdition = Sources['editions'][number] & { rev_ts?: string | null }
/** Fields the API adds beyond the contract: the last revision that still had the sentence. */
export type DroppedRow = Dropped['rows'][number] & { last_rev?: number | null; last_url?: string | null; time_precision?: string }

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message)
  }
}

/** The SQL of the latest API response, for the panel under every view. */
export const lastSql = shallowRef<{ path: string; method: string; statements: Statement[]; at: number } | null>(null)

type Params = Record<string, string | number | undefined | null>

export function url(path: string, params: Params = {}): string {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== '') q.set(k, String(v))
  const qs = q.toString()
  return qs ? `${path}?${qs}` : path
}

export async function getJson<T>(path: string, params: Params = {}, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(url(path, params), init)
  } catch {
    throw new ApiError(0, 'network', 'The API is not reachable.')
  }
  const body = await res.json().catch(() => null)
  if (!res.ok) {
    const err = body?.error ?? {}
    throw new ApiError(res.status, err.code ?? `http_${res.status}`, err.message ?? res.statusText)
  }
  if (Array.isArray(body?.sql))
    lastSql.value = { path, method: init?.method ?? 'GET', statements: body.sql as Statement[], at: Date.now() }
  return body as T
}

export const api = {
  health: () => getJson<Health>('/api/health'),
  topics: () => getJson<Topics>('/api/topics'),
  compare: (
    p: { topic: string; as_of?: string; anchor?: string; langs?: string; section?: string; offset?: number; limit?: number },
    init?: RequestInit,
  ) =>
    getJson<Compare>('/api/compare', p, init),
  dropped: (
    p: { topic?: string; lang?: string; reason?: string; min_days?: number; offset?: number; limit?: number },
    init?: RequestInit,
  ) => getJson<Dropped>('/api/dropped', p, init),
  check: (body: { text: string; as_of?: string; langs?: string[] }) =>
    getJson<Check>('/api/check', {}, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) }),
  checkRun: (runId: string, asOf?: string) => getJson<Check>(`/api/check/${encodeURIComponent(runId)}`, { as_of: asOf }),
  checkRecorded: () => getJson<CheckRecorded>('/api/check/recorded'),
  ask: (p: { q: string; as_of?: string; k?: number }, init?: RequestInit) => getJson<Ask>('/api/ask', p, init),
  sources: (p: { topic: string; as_of?: string }, init?: RequestInit) => getJson<Sources>('/api/sources', p, init),
  stats: () => getJson<Stats>('/api/stats'),
  timeline: (lang: string, pageId: number, h: string) =>
    getJson<Timeline>(`/api/claim/${encodeURIComponent(lang)}/${pageId}/${encodeURIComponent(h)}/timeline`),
}
