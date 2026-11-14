// Typed fetch for the Parallax API. Types come from contract/openapi.yaml (npm run types).
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

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message)
  }
}

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
  return body as T
}

export const api = {
  health: () => getJson<Health>('/api/health'),
  topics: () => getJson<Topics>('/api/topics'),
  compare: (p: { topic: string; as_of?: string; anchor?: string; langs?: string; offset?: number; limit?: number }, init?: RequestInit) =>
    getJson<Compare>('/api/compare', p, init),
  timeline: (lang: string, pageId: number, h: string) =>
    getJson<Timeline>(`/api/claim/${encodeURIComponent(lang)}/${pageId}/${encodeURIComponent(h)}/timeline`),
}
