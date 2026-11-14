// Slider points and the time axis shared by DateSlider and LifeBars.
export const FIRST_YEAR = 2003

export function todayIso(): string {
  return new Date().toISOString().slice(0, 10)
}

/** 1 January of every year from 2003, the exact dates in range, and '' for today, sorted. */
export function sliderPoints(exact: string[], today = todayIso()): string[] {
  const years: string[] = []
  for (let y = FIRST_YEAR; y <= Number(today.slice(0, 4)); y++) years.push(`${y}-01-01`)
  const inRange = exact.filter((d) => d >= `${FIRST_YEAR}-01-01` && d < today)
  return [...new Set([...years, ...inRange])].filter((d) => d <= today).sort().concat([''])
}

/** Index of the point nearest to an as_of value ('' is today). */
export function nearestIndex(points: string[], asOf: string): number {
  if (!asOf) return points.length - 1
  const t = Date.parse(asOf.slice(0, 10))
  let best = 0
  for (let i = 0; i < points.length; i++) {
    const p = points[i] ? Date.parse(points[i]) : Date.now()
    const b = points[best] ? Date.parse(points[best]) : Date.now()
    if (Math.abs(p - t) < Math.abs(b - t)) best = i
  }
  return best
}

/** Position of a timestamp on the axis from 1 January 2003 to now, as a fraction 0..1. */
export function axisFraction(iso: string | null | undefined, now = Date.now()): number {
  const start = Date.UTC(FIRST_YEAR, 0, 1)
  const t = iso ? Date.parse(iso) : now
  return Math.min(1, Math.max(0, (t - start) / (now - start)))
}
