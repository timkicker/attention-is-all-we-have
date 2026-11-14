import { describe, expect, it } from 'vitest'
import type { IngestRes } from '../api/types'
import { loadSearch, loadStart, toIngest, toResult } from './start'

const ed = (lang: string, state: 'waiting' | 'running' | 'done' | 'failed', pct: number, error: string | null = null) => ({
  lang,
  state,
  pct,
  error,
  retry_at: null,
})

const job = (over: Partial<IngestRes> = {}): IngestRes => ({
  job_id: 'Q152786',
  qid: 'Q152786',
  topic_id: 'mannerheim',
  title: 'Carl Gustaf Emil Mannerheim',
  state: 'running',
  eta_s: 240,
  since: null,
  editions: [ed('fi', 'done', 100), ed('sv', 'done', 100), ed('de', 'running', 91), ed('en', 'running', 28), ed('ru', 'waiting', 0), ed('et', 'waiting', 0), ed('uk', 'waiting', 0)],
  ...over,
})

const NOW = new Date('2026-11-14T12:00:00Z')

describe('toIngest', () => {
  it('averages edition progress and counts ready editions', () => {
    const vm = toIngest(job(), NOW)
    expect(vm.progress).toBe(46)
    expect(vm.readyCount).toBe(2)
    expect(vm.openHref).toBeNull()
    expect(vm.editions.map((e) => e.lang)).toEqual(['fi', 'sv', 'de', 'en', 'ru', 'et', 'uk'])
    expect(vm.faster).toEqual({ fromYear: 2021, toYear: 2026, since: '2021-01-01', etaS: 60 })
  })

  it('opens the comparison once usable', () => {
    const vm = toIngest(job({ state: 'usable' }), NOW)
    expect(vm.openHref).toBe('/t/Q152786')
  })

  it('drops the faster offer for a since-limited or finished job', () => {
    expect(toIngest(job({ since: '2021-01-01' }), NOW).faster).toBeNull()
    const done = toIngest(job({ state: 'done', editions: job().editions.map((e) => ({ ...e, state: 'done' as const })) }), NOW)
    expect(done.faster).toBeNull()
    expect(done.progress).toBe(100)
    expect(done.etaS).toBeNull()
  })

  it('fills missing editions as waiting and keeps API order fi first', () => {
    const vm = toIngest(job({ editions: [ed('uk', 'failed', 10, 'rate_limited'), ed('fi', 'done', 100)] }), NOW)
    expect(vm.editions[0]).toMatchObject({ lang: 'fi', state: 'done', pct: 100 })
    expect(vm.editions[6]).toMatchObject({ lang: 'uk', state: 'failed', error: 'rate_limited' })
    expect(vm.editions[1]).toMatchObject({ lang: 'sv', state: 'waiting', pct: 0 })
  })
})

describe('toIngest no_article', () => {
  it('leaves editions without an article out of the bar', () => {
    const eds = [ed('fi', 'done', 100), ed('sv', 'running', 50), ed('de', 'failed', 0, 'no_article'), ed('en', 'done', 100), ed('ru', 'done', 100), ed('et', 'done', 100), ed('uk', 'failed', 0, 'no_article')]
    expect(toIngest(job({ editions: eds }), NOW).progress).toBe(90)
  })
})

describe('search', () => {
  it('links by status', () => {
    const base = { qid: 'Q1', title: 'T', description: 'D', fi_title: null, eta_s: 360 }
    expect(toResult({ ...base, status: 'ready' }).href).toBe('/t/Q1')
    expect(toResult({ ...base, status: 'new' }).href).toBe('/t/Q1/loading')
    expect(toResult({ ...base, status: 'loading' }).href).toBe('/t/Q1/loading')
    expect(toResult({ ...base, status: 'no_finnish' }).href).toBeNull()
    expect(toResult({ ...base, description: 'defensive line', status: 'new' }).description).toBe('Defensive line')
  })

  it('does not call the API for an empty query and caps at six', async () => {
    let calls = 0
    const results = Array.from({ length: 9 }, (_, i) => ({ qid: `Q${i}`, title: 't', description: 'd', fi_title: null, status: 'new' as const, eta_s: 60 }))
    const api = { search: async () => (calls++, { ok: true as const, data: { results } }) } as never
    expect((await loadSearch(api, '  ')).ok).toBe(true)
    expect(calls).toBe(0)
    const r = await loadSearch(api, 'x')
    expect(r.ok && r.data.results.length).toBe(6)
  })
})

describe('loadStart', () => {
  it('lists loaded topics without years and shows the example only with Winter War', async () => {
    const topic = (qid: string, label: string) => ({ topic_id: label, label_en: label, wikidata_id: qid, depth: 'deep', editions: [] })
    const withWw = { topics: async () => ({ ok: true as const, data: { topics: [topic('Q134949', 'Winter War'), topic('Q152786', 'Mannerheim')] } }) } as never
    const r = await loadStart(withWw)
    expect(r.ok).toBe(true)
    if (!r.ok) return
    expect(r.data.prepared.map((p) => [p.title, p.from, p.href])).toEqual([
      ['Winter War', null, '/t/Q134949'],
      ['Mannerheim', null, '/t/Q152786'],
    ])
    expect(r.data.example?.href).toBe('/t/Q134949/s/fi/1256/abe24bc5f22fda02')
    const without = { topics: async () => ({ ok: true as const, data: { topics: [topic('Q152786', 'Mannerheim')] } }) } as never
    const r2 = await loadStart(without)
    expect(r2.ok && r2.data.example).toBeNull()
  })
})
