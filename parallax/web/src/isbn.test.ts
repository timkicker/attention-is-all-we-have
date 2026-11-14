import { describe, expect, it } from 'vitest'
import { isbnShares, mostly } from './isbn'

describe('isbn groups', () => {
  it('keeps the fixed order and folds unknown groups into other', () => {
    const s = isbnShares({ EN: 2, FI: 6, PL: 1, NO: 1 })
    expect(s.map((x) => x.group)).toEqual(['FI', 'EN', 'other'])
    expect(s[0].share).toBeCloseTo(0.6)
    expect(isbnShares({})).toEqual([])
  })
  it('names the group an edition cites mostly, only above half', () => {
    expect(mostly({ FI: 78, EN: 4 })).toEqual({ group: 'FI', n: 78, total: 82 })
    expect(mostly({ FI: 5, EN: 5 })).toBeNull()
  })
})
