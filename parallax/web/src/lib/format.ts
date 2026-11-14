// Formatting helpers. Dates "9 Jul 2014", numbers "26,662", name lists "Swedish, English and Russian".

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** "2014-07-09" or "2014-07-09T12:00:00Z" -> "9 Jul 2014" (read as UTC, never shifted by the local zone). */
export function fmtDate(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso)
  if (!m) return iso
  return `${Number(m[3])} ${MONTHS[Number(m[2]) - 1]} ${m[1]}`
}

/** "2014-07-09T12:00:00Z" -> "2014". */
export function fmtYear(iso: string): string {
  return iso.slice(0, 4)
}

/** 26662 -> "26,662". */
export function fmtNum(n: number): string {
  const [int, frac] = String(Math.abs(n)).split('.')
  const grouped = int.replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  return (n < 0 ? '-' : '') + grouped + (frac ? `.${frac}` : '')
}

/** ["Swedish", "English", "Russian"] -> "Swedish, English and Russian" (no Oxford comma). */
export function joinNames(names: readonly string[]): string {
  if (names.length <= 1) return names[0] ?? ''
  return `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`
}

const WORDS = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten']

/** 5 -> "five" up to ten, then digits with a comma ("same in the other five"). */
export function numWord(n: number): string {
  return WORDS[n] ?? fmtNum(n)
}

/** Seconds to whole minutes, rounded up, at least 1: 360 -> 6. */
export function minutes(seconds: number): number {
  return Math.max(1, Math.ceil(seconds / 60))
}

/** Today's date as YYYY-MM-DD in UTC. */
export function isoToday(now: Date = new Date()): string {
  return now.toISOString().slice(0, 10)
}

/** True for a real calendar date written YYYY-MM-DD. */
export function isIsoDate(s: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(s)) return false
  const d = new Date(`${s}T00:00:00Z`)
  return !Number.isNaN(d.getTime()) && d.toISOString().slice(0, 10) === s
}
