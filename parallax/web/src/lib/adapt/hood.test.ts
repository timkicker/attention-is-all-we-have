import { describe, expect, it } from 'vitest'
import type { TopicsRes } from '../api/types'
import type { SqlStatement } from '../api/types'
import { formatSql, fromStats, pickQuery, queryKind, shortGpu, versionsOf, prettySql } from './hood'

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

describe('fromStats', () => {
  it('reads recall, agreement and embedding rate', () => {
    const v = fromStats({
      judge_eval: { accuracy: 0.912, n: 120, alignment: { 'R@1': 0.57, 'R@5': 0.89 } },
      embed_rate: { per_s: 4555.2, gpu: 'NVIDIA A100-SXM4-80GB on Verda, bge-m3 fp16' },
    })
    expect(v).toEqual({ top1: 0.57, top5: 0.89, embedRate: 4555.2, embedGpu: 'A100 GPU, bge-m3', judgeAccuracy: 0.912, judgeN: 120 })
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

describe('stored matches', () => {
  it('picks the align read over the verdict lookup and says it reads stored matches', () => {
    const align = st('SELECT al.src_h, al.`rank` AS rnk FROM align al JOIN claim b ON 1', 750)
    const verdict = st('SELECT x.src_h, VEC_DISTANCE_COSINE(b.emb, a.emb) AS dist FROM (SELECT 1) x', 70)
    expect(pickQuery([verdict, align])).toBe(align)
    expect(queryKind(align)).toBe('stored')
    expect(queryKind(verdict)).toBe('vector')
  })
  it('shortens the GPU text and keeps unknown text', () => {
    expect(shortGpu('NVIDIA A100-SXM4-80GB on Verda, bge-m3 fp16')).toBe('A100 GPU, bge-m3')
    expect(shortGpu('laptop')).toBe('laptop')
  })
})

describe('formatSql', () => {
  it('writes the parameters in, lists as a count, one clause per line', () => {
    const s = st(
      '  SELECT a.h,   a.text\n  FROM claim FOR SYSTEM_TIME AS OF TIMESTAMP %(as_of)s AS a\n  WHERE a.topic_id = %(topic)s AND a.h IN %(hs)s AND %(section)s IS NULL AND %(q)s > \'\'  \n',
      3,
      { as_of: '2008-01-01 00:00:00', topic: "o'neil", hs: { count: 25 }, section: null, q: { chars: 500 } },
    )
    expect(formatSql(s)).toBe(
      [
        'SELECT a.h, a.text',
        'FROM claim',
        "  FOR SYSTEM_TIME AS OF TIMESTAMP '2008-01-01 00:00:00' AS a",
        "WHERE a.topic_id = 'o''neil'",
        '  AND a.h IN (/* 25 values */)',
        '  AND NULL IS NULL',
        "  AND '…' /* 500 characters */ > '';",
      ].join('\n'),
    )
  })
  it('leaves unknown placeholders as they are', () => {
    expect(formatSql(st('SELECT %(x)s', 1))).toBe('SELECT %(x)s;')
  })
})

describe('prettySql', () => {
  it('indents subqueries by two and keeps function parentheses whole', () => {
    const out = prettySql(
      'SELECT * FROM (\n  SELECT a.h, ROW_NUMBER() OVER (PARTITION BY a.h, b.lang ORDER BY d) AS rnk\n  FROM claim a JOIN claim b ON b.x = a.x AND b.y IN (1, 2)\n) c WHERE rnk <= 5 ORDER BY a.h',
    )
    expect(out).toBe(
      [
        'SELECT *',
        'FROM (',
        '  SELECT a.h, ROW_NUMBER() OVER (PARTITION BY a.h, b.lang ORDER BY d) AS rnk',
        '  FROM claim a',
        '  JOIN claim b',
        '    ON b.x = a.x',
        '    AND b.y IN (1, 2)',
        ') c',
        'WHERE rnk <= 5',
        'ORDER BY a.h',
      ].join('\n'),
    )
  })
  it('keeps quoted keywords and breaks long select lists after a comma', () => {
    expect(prettySql("SELECT 'a FROM b' AS t")).toBe("SELECT 'a FROM b' AS t")
    const out = prettySql('SELECT b.page_id, b.section, b.text, b.born_rev, b.died_rev, b.row_start FROM x').split('\n')
    expect(out.length).toBe(3)
    expect(out[1].startsWith('  ')).toBe(true)
    expect(out[2]).toBe('FROM x')
  })
})

