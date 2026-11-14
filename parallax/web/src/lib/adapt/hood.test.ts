import { describe, expect, it } from 'vitest'
import type { TopicsRes } from '../api/types'
import type { SqlStatement } from '../api/types'
import { formatSql, fromStats, pickQuery, versionsOf, wrapLine } from './hood'

const st = (text: string, rows: number, params?: SqlStatement['params']): SqlStatement => ({
  text,
  ms: 12.5,
  rows,
  index: 'none',
  params,
})

describe('pickQuery', () => {
  it('takes the vector statement with the most rows', () => {
    const a = st('SELECT lang FROM page', 900)
    const b = st('SELECT VEC_DISTANCE_COSINE(b.emb, a.emb) FROM claim', 750)
    const c = st('SELECT x, VEC_DISTANCE_COSINE(b.emb, a.emb) AS dist FROM verdict', 1)
    expect(pickQuery([a, c, b])).toBe(b)
  })
  it('gives null when no vector statement ran', () => {
    expect(pickQuery([st('SELECT 1', 1)])).toBeNull()
  })
})

describe('formatSql', () => {
  it('writes the parameters in, lists as a count, and dedents', () => {
    const s = st(
      '  SELECT *\n  FROM claim FOR SYSTEM_TIME AS OF TIMESTAMP %(as_of)s AS a\n  WHERE a.topic_id = %(topic)s AND a.h IN %(hs)s\n  AND a.x = %(n)s AND %(section)s IS NULL  \n',
      3,
      { as_of: '2008-01-01 00:00:00', topic: "o'neil", hs: { count: 25 }, n: 5, section: null },
    )
    expect(formatSql(s)).toBe(
      "SELECT *\nFROM claim FOR SYSTEM_TIME AS OF TIMESTAMP '2008-01-01 00:00:00' AS a\nWHERE a.topic_id = 'o''neil' AND a.h IN (/* 25 values */)\nAND a.x = 5 AND NULL IS NULL;",
    )
  })
  it('leaves unknown placeholders as they are', () => {
    expect(formatSql(st('SELECT %(x)s', 1))).toBe('SELECT %(x)s;')
  })
})

describe('fromStats', () => {
  it('reads recall, agreement and embedding rate', () => {
    const v = fromStats({
      judge_eval: { accuracy: 0.912, n: 120, alignment: { 'R@1': 0.57, 'R@5': 0.89 } },
      embed_rate: { per_s: 4555.2, gpu: 'A100 on Verda' },
    })
    expect(v).toEqual({ top1: 0.57, top5: 0.89, embedRate: 4555.2, embedGpu: 'A100 on Verda', judgeAccuracy: 0.912, judgeN: 120 })
  })
  it('gives null for every missing stat, never a made-up number', () => {
    expect(fromStats({ embed_rate: { laptop_ollama: 19.98 } })).toEqual({
      top1: null,
      top5: null,
      embedRate: null,
      embedGpu: null,
      judgeAccuracy: null,
      judgeN: null,
    })
    expect(fromStats(null).top1).toBeNull()
  })
})

describe('versionsOf', () => {
  const topics = {
    topics: [
      {
        topic_id: 'winterwar',
        label_en: 'Winter War',
        wikidata_id: 'Q134949',
        depth: 'deep',
        editions: [
          { lang: 'fi', revisions: 2143 },
          { lang: 'sv', revisions: 781 },
        ],
      },
    ],
    sql: [],
  } as unknown as TopicsRes
  it('adds the revisions of every edition', () => {
    expect(versionsOf(topics, 'winterwar')).toBe(2924)
  })
  it('gives null for an unknown topic', () => {
    expect(versionsOf(topics, 'nope')).toBeNull()
  })
})

describe('wrapLine', () => {
  it('breaks long lines after a comma and indents the rest', () => {
    const line = '  SELECT ' + Array.from({ length: 12 }, (_, i) => `b.column_${i}`).join(', ')
    const out = wrapLine(line, 40)
    expect(out.length).toBeGreaterThan(1)
    expect(out.every((l) => l.length <= 40)).toBe(true)
    expect(out.slice(1).every((l) => l.startsWith('    '))).toBe(true)
    expect(out.map((l) => l.trim()).join(' ')).toBe(line.trim())
  })
  it('keeps short lines and lines without a comma', () => {
    expect(wrapLine('SELECT 1', 40)).toEqual(['SELECT 1'])
    expect(wrapLine('x'.repeat(50), 40)).toEqual(['x'.repeat(50)])
  })
})

describe('wrapLine keeps calls whole', () => {
  it('never breaks inside parentheses and falls back to keywords', () => {
    const line = '  JOIN claim FOR SYSTEM_TIME AS OF TIMESTAMP x AS b IGNORE INDEX (emb), VEC_DISTANCE_COSINE(b.emb, a.emb) AS d'
    const out = wrapLine(line, 60)
    expect(out.some((l) => l.includes('VEC_DISTANCE_COSINE(b.emb, a.emb)'))).toBe(true)
    expect(out.some((l) => l.trimStart().startsWith('IGNORE INDEX'))).toBe(true)
  })
})
