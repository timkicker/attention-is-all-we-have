// Fetch wrappers for every API route. Nothing throws: each call returns Result<T>, and a failure
// carries the HTTP status, the API's error code and, for 429, the seconds to wait (body
// retry_after_s, else the Retry-After header).

import type { Failure, Result } from '../model'
import type {
  ApiErrorBody,
  CheckRecordedRes,
  CheckReq,
  CheckRes,
  CompareRes,
  DroppedRes,
  HealthRes,
  IngestReq,
  IngestRes,
  Reason,
  SearchRes,
  SqlPanelRes,
  StatsRes,
  TimelineRes,
  TopicsRes,
} from './types'

type Query = Record<string, string | number | null | undefined>

function qs(q: Query): string {
  const p = new URLSearchParams()
  for (const [k, v] of Object.entries(q)) if (v !== null && v !== undefined && v !== '') p.set(k, String(v))
  const s = p.toString()
  return s ? `?${s}` : ''
}

async function call<T>(path: string, init?: RequestInit & { json?: unknown }): Promise<Result<T>> {
  let res: Response
  try {
    const { json, ...rest } = init ?? {}
    res = await fetch(path, {
      ...rest,
      headers: { Accept: 'application/json', ...(json !== undefined ? { 'Content-Type': 'application/json' } : {}) },
      body: json !== undefined ? JSON.stringify(json) : rest.body,
    })
  } catch (e) {
    return { ok: false, error: { status: 0, code: 'network', message: String(e) } }
  }
  let body: unknown = null
  try {
    body = await res.json()
  } catch {
    body = null
  }
  if (res.ok) return { ok: true, data: body as T }
  const err = (body as ApiErrorBody | null)?.error
  const failure: Failure = {
    status: res.status,
    code: typeof err?.code === 'string' ? err.code : `http_${res.status}`,
    message: typeof err?.message === 'string' ? err.message : res.statusText,
  }
  if (res.status === 429) {
    const header = Number(res.headers.get('Retry-After'))
    const fromBody = typeof err?.retry_after_s === 'number' ? err.retry_after_s : NaN
    const s = Number.isFinite(fromBody) ? fromBody : Number.isFinite(header) ? header : NaN
    if (Number.isFinite(s)) failure.retryAfterS = s
  }
  return { ok: false, error: failure }
}

export const api = {
  health: () => call<HealthRes>('/api/health'),
  topics: () => call<TopicsRes>('/api/topics'),
  compare: (q: { topic: string; as_of?: string; anchor?: string; h?: string; langs?: string; section?: string; offset?: number; limit?: number }) =>
    call<CompareRes>(`/api/compare${qs(q)}`),
  timeline: (lang: string, pageId: number | string, h: string) =>
    call<TimelineRes>(`/api/claim/${encodeURIComponent(lang)}/${encodeURIComponent(String(pageId))}/${encodeURIComponent(h)}/timeline`),
  dropped: (q: { topic?: string; lang?: string; reason?: Reason; min_days?: number; offset?: number; limit?: number }) =>
    call<DroppedRes>(`/api/dropped${qs(q)}`),
  check: (req: CheckReq) => call<CheckRes>('/api/check', { method: 'POST', json: req }),
  checkRecorded: () => call<CheckRecordedRes>('/api/check/recorded'),
  checkRun: (runId: string, asOf?: string) => call<CheckRes>(`/api/check/${encodeURIComponent(runId)}${qs({ as_of: asOf })}`),
  stats: () => call<StatsRes>('/api/stats'),
  sqlPanel: (panelId: string) => call<SqlPanelRes>(`/api/sql/${encodeURIComponent(panelId)}`),
  search: (q: string) => call<SearchRes>(`/api/search${qs({ q })}`),
  startIngest: (req: IngestReq) => call<IngestRes>('/api/ingest', { method: 'POST', json: req }),
  ingest: (qid: string) => call<IngestRes>(`/api/ingest/${encodeURIComponent(qid)}`),
}
