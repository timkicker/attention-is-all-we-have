import { describe, expect, it } from 'vitest'
import { highlight } from './highlight'

describe('highlight', () => {
  it('marks the first occurrence of each needle, case insensitive', () => {
    expect(highlight('25,904 people died; 25,904 again', [{ text: '25,904', kind: 'number' }])).toEqual([
      { text: '25,904', kind: 'number' },
      { text: ' people died; 25,904 again' },
    ])
    expect(highlight('An incident was Reported', [{ text: 'reported', kind: 'term' }]).at(-1)).toEqual({
      text: 'Reported',
      kind: 'term',
    })
  })
  it('keeps text whole when a needle is missing or overlaps', () => {
    expect(highlight('abc', [{ text: 'x', kind: 'term' }])).toEqual([{ text: 'abc' }])
    expect(
      highlight('staged it', [
        { text: 'staged', kind: 'term' },
        { text: 'aged', kind: 'term' },
      ]).length,
    ).toBe(2)
  })
})
