// Seven editions of reference counts in the shape of contract/examples/sources.json, for UI tests only.
const LANGS = ['fi', 'sv', 'de', 'en', 'ru', 'et', 'uk']
export const sources7 = {
  as_of: '2026-11-14T00:00:00Z',
  editions: LANGS.map((lang, i) => ({
    lang,
    rev_id: 1000 + i,
    rev_ts: '2026-11-01T00:00:00Z',
    refs: 100 + i,
    isbn: lang === 'fi' ? { FI: 78, EN: 3, SE: 1 } : { EN: 40, FI: 5, PL: 2 },
    domains: { 'books.google.com': 9, 'yle.fi': 4 },
  })),
  sql: [{ text: 'SELECT lang, rev_id FROM ref_stat FOR SYSTEM_TIME AS OF TIMESTAMP %(as_of)s', ms: 0.5, rows: 7, index: 'none' }],
}
