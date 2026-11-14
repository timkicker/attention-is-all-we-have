import { describe, expect, it } from 'vitest'
import { axisFraction, nearestIndex, sliderPoints } from './timeaxis'

describe('slider points', () => {
  const pts = sliderPoints(['2009-08-21', '2014-07-09', '1999-01-01'], '2026-11-14')
  it('has 1 January of every year, exact dates in range and today last', () => {
    expect(pts[0]).toBe('2003-01-01')
    expect(pts).toContain('2009-08-21')
    expect(pts).toContain('2014-07-09')
    expect(pts).not.toContain('1999-01-01')
    expect(pts.at(-2)).toBe('2026-01-01')
    expect(pts.at(-1)).toBe('')
    expect(pts.indexOf('2009-08-21')).toBe(pts.indexOf('2009-01-01') + 1)
  })
  it('finds the nearest point for any date', () => {
    expect(pts[nearestIndex(pts, '')]).toBe('')
    expect(pts[nearestIndex(pts, '2008-06-01')]).toBe('2008-01-01')
    expect(pts[nearestIndex(pts, '2009-08-20')]).toBe('2009-08-21')
  })
  it('maps dates on the axis', () => {
    expect(axisFraction('2003-01-01T00:00:00Z')).toBe(0)
    expect(axisFraction(null)).toBe(1)
  })
})
