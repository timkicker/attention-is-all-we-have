import { describe, expect, it } from 'vitest'
import type { api as Api } from '../api/client'
import { noteText } from '../copy'
import type { TopicCtx } from './shared'
import { countRemoved, cutOf, forgetRemoved, loadRemoved, PAGE, type DroppedRowRaw } from './removed'

const ctx = (date: string | null = null): TopicCtx => ({
  topic: { qid: 'Q134949', topicId: 'winterwar', title: 'Winter War' },
  date,
  asOf: date ?? '2026-11-14',
})

function raw(i: number, over: Partial<DroppedRowRaw> = {}): DroppedRowRaw {
  return {
    lang: 'sv',
    page_id: 1,
    title: 'Vinterkriget',
    h: `h${i}`,
    text: `Statement number ${i} about volunteers`,
    gloss: null,
    born: '2004-01-01T00:00:00Z',
    died: '2021-03-03T10:00:00Z',
    died_rev: 5,
    died_comment: null,
    days: 400,
    reason: 'none',
    alive_in: [
      { lang: 'fi', h: 'a', text: 'x', verdict: { label: 'same' }, oldid_url: '' },
      { lang: 'de', h: 'b', text: 'y', verdict: { label: 'partial' }, oldid_url: '' },
    ],
    removed: null,
    ...over,
  }
}

function fakeApi(rows: DroppedRowRaw[]) {
  const calls: { offset?: number; limit?: number }[] = []
  const api = {
    dropped: async (q: { offset?: number; limit?: number }) => {
      calls.push(q)
      const o = q.offset ?? 0
      return { ok: true, data: { total: rows.length, rows: rows.slice(o, o + (q.limit ?? 25)), scale: {}, sql: [] } }
    },
  } as unknown as typeof Api
  return { api, calls }
}

describe('cutOf', () => {
  it('strikes the whole sentence when nothing else is known', () => {
    const c = cutOf({ text: 'About 12,000 volunteers', gloss: null, removed: null })
    expect(c.what).toBe('all')
    expect(c.say.spans).toEqual([{ start: 0, end: 23 }])
  })
  it('uses the English gloss for a whole removal', () => {
    expect(cutOf({ text: 'Noin 12 000', gloss: 'About 12,000', removed: null }).say.text).toBe('About 12,000')
  })
  it('names the end and a cut in the middle', () => {
    const text = 'Stalin expected Helsinki within twelve days.'
    expect(cutOf({ text, gloss: null, removed: { start: 25, end: text.length } }).what).toBe('end')
    const mid = cutOf({ text: 'The Soviet Union staged the shots', gloss: null, removed: { start: 17, end: 23 } })
    expect(mid.what).toEqual({ words: 'staged' })
    expect(mid.say.spans).toEqual([{ start: 17, end: 23 }])
  })
})

describe('loadRemoved', () => {
  it('loads every page once, notes the edition and pages on the client', async () => {
    forgetRemoved()
    const rows = Array.from({ length: 230 }, (_, i) => raw(i))
    const { api, calls } = fakeApi(rows)
    const r = await loadRemoved(api, ctx(), { q: '', offset: 0, edition: null })
    if (!r.ok) throw new Error('failed')
    expect(calls.map((c) => c.offset)).toEqual([0, 200])
    expect(r.data.total).toBe(230)
    expect(r.data.rows).toHaveLength(PAGE)
    expect(r.data.more).toBe(230 - PAGE)
    expect(noteText(r.data.rows[0].note)).toBe('Swedish removed all of it on 3 Mar 2021 · still in Finnish and German')
    expect(r.data.rows[0].href).toBe('/t/Q134949/s/sv/1/h0')
    const next = await loadRemoved(api, ctx(), { q: '', offset: PAGE, edition: null })
    expect(next.ok && next.data.rows.length).toBe(2 * PAGE)
    expect(calls).toHaveLength(2) // cached
  })

  it('filters by edition, text and date', async () => {
    forgetRemoved()
    const rows = [raw(1), raw(2, { lang: 'ru', text: 'Losses were 126,875' }), raw(3, { died: '2010-01-01T00:00:00Z' })]
    const { api } = fakeApi(rows)
    const ru = await loadRemoved(api, ctx(), { q: '', offset: 0, edition: 'ru' })
    expect(ru.ok && ru.data.rows.map((x) => x.id)).toEqual(['ru:1:h2'])
    expect(ru.ok && ru.data.editions).toEqual(['sv', 'ru'])
    const q = await loadRemoved(api, ctx(), { q: 'LOSSES', offset: 0, edition: null })
    expect(q.ok && q.data.total).toBe(1)
    const past = await loadRemoved(api, ctx('2015-01-01'), { q: '', offset: 0, edition: null })
    expect(past.ok && past.data.rows.map((x) => x.id)).toEqual(['sv:1:h3'])
    expect(await countRemoved(api, ctx())).toBe(3)
    expect(await countRemoved(api, ctx('2015-01-01'))).toBe(1)
  })
})
