// Five atlas topics in the shape of contract/examples/atlas.json, for UI tests only (numbers are made up).
export const atlas5 = {
  counts: { all: 2, 'fi+sv': 1, 'fi+en': 1, fi: 1 },
  topics: [
    { wikidata_id: 'Q1', titles: { fi: 'Maailmankaikkeus', sv: 'Universum', en: 'Universe' }, coverage: 'all', dist: { fi_sv: 0.3, fi_en: 0.05, sv_en: 0.2 }, topic_id: null },
    { wikidata_id: 'Q20', titles: { fi: 'Norja', sv: 'Norge', en: null }, coverage: 'fi+sv', dist: { fi_sv: 0.4, fi_en: null, sv_en: null }, topic_id: null },
    { wikidata_id: 'Q33', titles: { fi: 'Suomi', sv: null, en: 'Finland' }, coverage: 'fi+en', dist: { fi_sv: null, fi_en: 0.25, sv_en: null }, topic_id: null },
    { wikidata_id: 'Q99', titles: { fi: 'Pikkukylä', sv: null, en: null }, coverage: 'fi', dist: { fi_sv: null, fi_en: null, sv_en: null }, topic_id: null },
    { wikidata_id: 'Q134949', titles: { fi: 'Talvisota', sv: 'Vinterkriget', en: 'Winter War' }, coverage: 'all', dist: { fi_sv: 0.12, fi_en: 0.14, sv_en: 0.11 }, topic_id: 'winterwar' },
  ],
  sql: [{ text: 'SELECT coverage, COUNT(*) AS n FROM atlas_topic GROUP BY coverage', ms: 0.4, rows: 4, index: 'none' }],
}
