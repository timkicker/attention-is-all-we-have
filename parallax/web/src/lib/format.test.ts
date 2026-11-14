import { describe, expect, it } from 'vitest'
import { fmtDate, fmtNum, isIsoDate, joinNames, minutes, numWord } from './format'

describe('format', () => {
  it('writes dates as "9 Jul 2014"', () => {
    expect(fmtDate('2014-07-09')).toBe('9 Jul 2014')
    expect(fmtDate('2026-11-14T00:00:00Z')).toBe('14 Nov 2026')
  })
  it('groups thousands with a comma', () => {
    expect(fmtNum(26662)).toBe('26,662')
    expect(fmtNum(450000)).toBe('450,000')
    expect(fmtNum(62)).toBe('62')
    expect(fmtNum(0.57)).toBe('0.57')
  })
  it('joins names without an Oxford comma', () => {
    expect(joinNames(['Swedish', 'English', 'Russian'])).toBe('Swedish, English and Russian')
    expect(joinNames(['German', 'English'])).toBe('German and English')
    expect(joinNames(['Swedish'])).toBe('Swedish')
    expect(joinNames([])).toBe('')
  })
  it('writes small numbers as words', () => {
    expect(numWord(5)).toBe('five')
    expect(numWord(12)).toBe('12')
  })
  it('rounds minutes up, at least one', () => {
    expect(minutes(360)).toBe(6)
    expect(minutes(10)).toBe(1)
  })
  it('accepts only real dates', () => {
    expect(isIsoDate('2008-01-01')).toBe(true)
    expect(isIsoDate('2008-02-30')).toBe(false)
    expect(isIsoDate('1.1.2008')).toBe(false)
  })
})
