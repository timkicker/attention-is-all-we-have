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

  it('hides the faster offer with two minutes or less left', () => {
    expect(toIngest(job({ eta_s: 120 }), NOW).faster).toBeNull()
    expect(toIngest(job({ eta_s: 121 }), NOW).faster).not.toBeNull()
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

const cell = (over: Record<string, unknown>) => ({
  status: 'matched', h: 'x', page_id: 1, text: null, gloss: null, dist: null, verdict: null, marks: [],
  born: null, died: null, born_rev: null, died_rev: null, time_precision: null, oldid_url: null, ...over,
})
const term = (other: string, thisEn: string | null = 'staged') => ({ kind: 'term', this: 'lavasti', other, this_en: thisEn })
const mainila = (cells: Record<string, unknown>) => ({
  topic: 'winterwar', as_of: '', anchor: 'fi', langs: [], editions: {}, total_rows: 1, sql: [],
  rows: [{ row_id: 'r', section: 's', cells: {
    fi: cell({ status: 'anchor', h: 'abe24bc5f22fda02', page_id: 1256, text: 'Neuvostoliitto lavasti', gloss: 'On 26 November 1939, the Soviet Union staged the Shelling of Mainila' }),
    ...cells,
  } }],
})
const FULL = mainila({
  sv: cell({ text: 'Den officiella', gloss: 'The official Soviet explanation referred to Mainila.', marks: [term('Den officiella')] }),
  de: cell({ text: 'Am 26.', gloss: 'The Red Army staged a border incident', marks: [term('die Rote Armee', null)] }),
  en: cell({ text: 'On 26 November 1939, an incident was reported near Mainila', marks: [term('was reported')] }),
  ru: cell({ text: 'организовал', gloss: 'The Soviet Union organized a provocation', marks: [term('организовал провокацию')] }),
  et: cell({ text: 'x', gloss: 'Finland had fired', marks: [term('None')] }),
})
const topic = (qid: string, label: string) => ({ topic_id: label === 'Winter War' ? 'winterwar' : label, label_en: label, wikidata_id: qid, depth: 'deep', editions: [] })
const client = (topics: unknown[], compare: unknown) =>
  ({
    topics: async () => ({ ok: true as const, data: { topics } }),
    compare: async (q: { h?: string }) => (q.h === 'abe24bc5f22fda02' ? compare : { ok: false, error: { status: 404, code: 'x', message: '' } }),
  }) as never

describe('loadStart', () => {
  it('builds the example from the real statement: Finnish plus three differing editions', async () => {
    const r = await loadStart(client([topic('Q134949', 'Winter War'), topic('Q152786', 'Mannerheim')], { ok: true, data: FULL }))
    expect(r.ok).toBe(true)
    if (!r.ok) return
    expect(r.data.prepared.map((p) => [p.title, p.from, p.href, 'editions' in p ? p.editions : null])).toEqual([
      ['Winter War', null, '/t/Q134949', 0],
      ['Mannerheim', null, '/t/Q152786', 0],
    ])
    const ex = r.data.example!
    expect(ex.href).toBe('/t/Q134949/s/fi/1256/abe24bc5f22fda02')
    expect(ex.title).toBe('How four editions tell the Mainila shots')
    expect(ex.lines.map((l) => l.lang)).toEqual(['fi', 'sv', 'en', 'ru'])
    const markedWords = ex.lines.map((l) => l.say.spans.map((s) => l.say.text.slice(s.start, s.end)))
    expect(markedWords).toEqual([['staged'], [], ['was reported'], []])
  })

  it('puts Winter War first and keeps the API order for the rest', async () => {
    const r = await loadStart(client([topic('Q1', 'A'), topic('Q134949', 'Winter War'), topic('Q2', 'B')], { ok: true, data: FULL }))
    expect(r.ok && r.data.prepared.map((p) => p.title)).toEqual(['Winter War', 'A', 'B'])
  })

  it('hides the example without Winter War, on a failed call or with fewer than two differing editions', async () => {
    expect(((await loadStart(client([topic('Q152786', 'M')], { ok: true, data: FULL }))) as { data: { example: unknown } }).data.example).toBeNull()
    const failed = await loadStart(client([topic('Q134949', 'Winter War')], { ok: false, error: { status: 500, code: 'x', message: '' } }))
    expect(failed.ok && failed.data.example).toBeNull()
    const one = mainila({ en: cell({ text: 'an incident was reported', marks: [term('was reported')] }) })
    const r = await loadStart(client([topic('Q134949', 'Winter War')], { ok: true, data: one }))
    expect(r.ok && r.data.example).toBeNull()
  })
})
