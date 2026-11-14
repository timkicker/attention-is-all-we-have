// ISBN groups as A14 counts them, in a fixed order that also fixes their colour (never by rank).
export const ISBN_GROUPS = ['FI', 'SE', 'DE', 'EN', 'RU', 'EE', 'UA'] as const
export const OTHER = 'other'

export const ISBN_NAMES: Record<string, string> = {
  FI: 'Finland',
  SE: 'Sweden',
  DE: 'German language',
  EN: 'English language',
  RU: 'Russia and the USSR',
  EE: 'Estonia',
  UA: 'Ukraine',
  [OTHER]: 'other groups',
}

/** Shares per group in the fixed order, everything else folded into "other". */
export function isbnShares(isbn: Record<string, number>): { group: string; n: number; share: number }[] {
  const total = Object.values(isbn).reduce((a, b) => a + b, 0)
  if (!total) return []
  const other = Object.entries(isbn)
    .filter(([g]) => !(ISBN_GROUPS as readonly string[]).includes(g))
    .reduce((a, [, n]) => a + n, 0)
  return [...ISBN_GROUPS.map((g) => ({ group: g as string, n: isbn[g] ?? 0 })), { group: OTHER, n: other }]
    .filter((x) => x.n > 0)
    .map((x) => ({ ...x, share: x.n / total }))
}

/** "cites mostly FI" when one group holds more than half of the ISBNs, else null. */
export function mostly(isbn: Record<string, number>): { group: string; n: number; total: number } | null {
  const total = Object.values(isbn).reduce((a, b) => a + b, 0)
  const top = Object.entries(isbn).sort((a, b) => b[1] - a[1])[0]
  return top && top[1] * 2 > total ? { group: top[0], n: top[1], total } : null
}
