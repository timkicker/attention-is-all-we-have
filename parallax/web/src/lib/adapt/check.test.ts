import { describe, expect, it } from 'vitest'
import type { CheckRes } from '../api/types'
import * as copy from '../copy'
import { modelName, pickRecorded, recordedLabel, toCheckRow, toResult } from './check'
import type { TopicCtx } from './shared'

const ctx: TopicCtx = { topic: { qid: 'Q134949', topicId: 'winterwar', title: 'Winter War' }, date: null, asOf: '2026-11-14' }
type Label = 'says' | 'stopped_saying' | 'contradicts' | 'not_found'

function ev(lang: string, died: string | null = null) {
  return { lang, page_id: 7, h: `h-${lang}`, text: 't', born: '2005-01-01T00:00:00Z', died, died_rev: null, died_comment: null, dist: 0.1, verdict: null, oldid_url: '' }
}
function claim(idx: number, labels: Record<string, Label>, died: Record<string, string> = {}): CheckRes['claims'][number] {
  return {
    idx,
    text: `Statement ${idx}`,
    per_lang: Object.fromEntries(
      Object.entries(labels).map(([l, label]) => [l, { label, evidence: label === 'not_found' ? [] : [ev(l, died[l] ?? null)] }]),
    ),
  }
}
const seven = (f: (l: string) => Label): Record<string, Label> =>
  Object.fromEntries(['fi', 'sv', 'de', 'en', 'ru', 'et', 'uk'].map((l) => [l, f(l)]))

describe('recorded labels come from the data', () => {
  it('model family on the question', () => {
    expect(modelName('gemini-3.8-flash')).toBe('Gemini')
    expect(recordedLabel({ answer_model: 'gemma-4-31b-it', question: 'When did the Winter War end?' })).toBe("Gemma on the war's end")
    expect(recordedLabel({ answer_model: null, question: null })).toBeNull()
    // the five real questions of contract/fixtures/answers.json get a short topic phrase
    const real = [
      'Who fired the shots at Mainila in November 1939?',
      'How many Finnish soldiers died in the Winter War?',
      'How much territory did Finland cede to the Soviet Union after the Winter War?',
      'When did the Winter War end?',
      'What was the Terijoki government?',
    ]
    expect(real.map((question) => recordedLabel({ answer_model: 'gemini-3.8-flash', question }))).toEqual([
      'Gemini on Mainila',
      'Gemini on Finnish losses',
      'Gemini on ceded land',
      "Gemini on the war's end",
      'Gemini on Terijoki',
    ])
    expect(real.every((question) => (recordedLabel({ answer_model: 'gemini-3.8-flash', question }) ?? '').length <= 30)).toBe(true)
    const long = recordedLabel({ answer_model: 'm', question: `${'word '.repeat(20)}end?` })
    expect(long).toBe(`M on ${'word '.repeat(16).trim()}`)
  })
  it('offers different questions first', () => {
    const r = (id: string, q: string) => ({ run_id: id, question: q, answer_model: 'm', answer_date: null })
    expect(pickRecorded([r('1', 'a'), r('2', 'a'), r('3', 'b')], 2).map((x) => x.run_id)).toEqual(['1', '3'])
    const qs = ['When did the Winter War end?', 'How many Finnish soldiers died in the Winter War?', 'Who fired the shots at Mainila in November 1939?']
    expect(pickRecorded(qs.map((q, i) => r(String(i), q))).map((x) => x.question)).toEqual([qs[2], qs[1], qs[0]])
    const fx = { run_id: 'fx', question: 'What happened at Mainila?', answer_model: 'example answer (test fixture)', answer_date: null }
    expect(pickRecorded([fx, r('9', qs[2])]).map((x) => x.run_id)).toEqual(['9', 'fx'])
  })
})

describe('row lines', () => {
  it('in no edition', () => {
    const row = toCheckRow('Q134949', claim(0, seven(() => 'not_found')))
    expect([row.verdict, row.head, row.href]).toEqual(['none', ['In no edition'], null])
  })
  it('contradicted', () => {
    const row = toCheckRow('Q134949', claim(0, seven((l) => (l === 'sv' || l === 'ru' ? 'contradicts' : 'says'))))
    expect([row.verdict, row.head]).toEqual(['disputed', ['Disputed', 'Swedish and Russian say otherwise']])
  })
  it('removed by one edition', () => {
    const labels = seven((l) => (['fi', 'de', 'uk'].includes(l) ? 'says' : l === 'en' ? 'stopped_saying' : 'not_found'))
    const row = toCheckRow('Q134949', claim(0, labels, { en: '2009-12-31T20:28:48Z' }))
    expect([row.verdict, row.head]).toEqual(['disputed', ['Disputed', 'in 3 of 7', 'English removed it in 2009']])
    expect(row.href).toBe('/t/Q134949/s/fi/7/h-fi')
  })
  it('removed by more than two editions, in at most half', () => {
    const labels = seven((l) => (['fi', 'de'].includes(l) ? 'says' : ['en', 'sv', 'et'].includes(l) ? 'stopped_saying' : 'not_found'))
    const died = { en: '2009-12-31T20:28:48Z', sv: '2012-01-01T00:00:00Z', et: '2015-01-01T00:00:00Z' }
    expect(toCheckRow('Q134949', claim(0, labels, died)).head).toEqual(['Disputed', 'in 2 of 7', '3 editions removed it'])
  })
  it('removed by one but still in most editions is backed', () => {
    const labels = seven((l) => (l === 'en' ? 'stopped_saying' : l === 'et' ? 'not_found' : 'says'))
    const row = toCheckRow('Q134949', claim(0, labels, { en: '2009-12-31T20:28:48Z' }))
    expect([row.verdict, row.head]).toEqual(['backed', ['Backed by 5 of 7 editions']])
  })
  it('removed everywhere is in no edition, never disputed', () => {
    const row = toCheckRow('Q134949', claim(0, seven((l) => (l === 'fi' ? 'stopped_saying' : 'not_found')), { fi: '2010-01-01T00:00:00Z' }))
    expect([row.verdict, row.head, row.href]).toEqual(['none', ['In no edition'], null])
  })
  it('backed', () => {
    const row = toCheckRow('Q134949', claim(0, seven((l) => (l === 'et' ? 'not_found' : 'says'))))
    expect([row.verdict, row.head]).toEqual(['backed', ['Backed by 6 of 7 editions']])
  })
  it('backed only by the similarity guess reads likely', () => {
    const c = claim(0, seven((l) => (l === 'et' ? 'not_found' : 'says')))
    for (const v of Object.values(c.per_lang)) for (const e of v.evidence) e.verdict = { label: 'partial', model: 'fake-judge-similarity' }
    expect(toCheckRow('Q134949', c).head).toEqual(['Likely backed by 6 of 7 editions (matched by shared names and numbers, no model)'])
  })
})

describe('result', () => {
  const base = { run_id: 'r1', source: 'recorded' as const, answer_model: 'gemini-3.8-flash', answer_date: '2026-11-12', engine: 'fake' as const, sql: [] }
  it('counts and says "most" only when true', () => {
    const d = { ...base, question: 'Who fired the shots at Mainila?', text: 'Whole answer.', claims: [
      claim(0, seven(() => 'says')),
      claim(1, seven((l) => (l === 'sv' ? 'contradicts' : 'says'))),
      claim(2, seven(() => 'not_found')),
    ] }
    const r = toResult(ctx, d)
    expect(r.summary).toEqual({ total: 3, none: 1, disputed: 1, backed: 1 })
    expect(r.rows.map((x) => x.verdict)).toEqual(['disputed', 'none', 'backed'])
    expect(r.label).toBe('Gemini on Mainila')
    expect(r.answer).toBe('Whole answer.')
    expect(copy.checkSummary(r.summary, r.mostBacked)).toBe('Of 3 statements, 1 is in no edition, 1 is disputed and 1 is backed by most editions')
    const few = toResult(ctx, { ...d, claims: [claim(0, seven((l) => (l === 'sv' ? 'says' : 'not_found')))] })
    expect(copy.checkSummary(few.summary, few.mostBacked)).toBe('Of 1 statement, 1 is backed by at least one edition')
  })
  it('a pasted answer has no label', () => {
    expect(toResult(ctx, { ...base, source: 'live', claims: [] }).label).toBeNull()
  })
})
