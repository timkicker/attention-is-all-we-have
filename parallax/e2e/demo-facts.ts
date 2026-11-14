// What the demo script (PLAN section 0) shows, per seed. demo.spec.ts picks the entry for the seed /api/health reports.
// Only what the audience reads is written here: sentences, terms, dates, edit comments and Wikipedia revision ids.
// Row ids (claim hashes) depend on how a seed split the text, so demo.spec.ts finds the rows through the API.
export interface DemoFacts {
  // the fi Mainila sentence: its section and words that pick it out of that section
  mainila: { section: string; words: string[]; terms: Record<string, string>; chip: string }
  // the fi Finnish dead sentence and the editions whose number differs
  dead: { section: string; fi: string; differs: string[] }
  // the en Mainila sentence before and after the 2009 edit, in the Time view of the fi sentence alive before it
  enFlip: { before: string; after: string; beforeText: string; afterText: string; comment: string | null }
  // the ru clause dropped in 2014 (v1: in 2017) and an edition that still states it
  ruDropped: { text: string; date: string; oldid: number; alive: string }
  fiScale: boolean
}

const MAINILA_SECTION = 'Suomen ja Neuvostoliiton neuvottelut aluemuutoksista'
const MAINILA_WORDS = ['lavasti', 'Mainilan laukaukset']
const DEAD = { section: 'Osapuolten tappiot', fi: '26 662' }
const RU_CLAUSE = 'инсценированный советской стороной'

export const FACTS: Record<string, DemoFacts> = {
  v1: {
    mainila: {
      section: MAINILA_SECTION,
      words: MAINILA_WORDS,
      terms: { de: 'inszenierte', sv: 'kunnat bevisas', en: 'reported' },
      chip: 'same claim',
    },
    dead: { ...DEAD, differs: ['sv', 'en'] },
    // v1 has yearly snapshots: the en sentence is gone in the snapshot after 2009
    enFlip: {
      before: '2008-01-01',
      after: '2018-01-01',
      beforeText: 'the Soviets staged the Shelling of Mainila',
      afterText: 'an incident was reported',
      comment: null,
    },
    ruDropped: { text: RU_CLAUSE, date: '23 Dec 2017', oldid: 60401111, alive: 'de: same claim' },
    fiScale: false,
  },
  v3: {
    mainila: {
      section: MAINILA_SECTION,
      words: MAINILA_WORDS,
      terms: { de: 'inszenierte', sv: 'kunnat bevisas', en: 'reported' },
      chip: 'same claim',
    },
    dead: { ...DEAD, differs: ['sv', 'en'] },
    enFlip: {
      before: '2009-08-01',
      after: '2009-09-01',
      beforeText: 'the Soviets staged the Shelling of Mainila',
      afterText: 'an incident was reported',
      comment: 'rewrote the mainila incident part',
    },
    ruDropped: { text: RU_CLAUSE, date: '9 Jul 2014', oldid: 63917953, alive: 'de: same claim' },
    fiScale: true,
  },
  // v4: the judge (judge-v1) labels these pairs "partial"; the nearest sv partial match is the official account
  // sentence. The fi sentence was reworded on 12 Sep 2026, so Time follows the 2007 to 2026 one.
  v4: {
    mainila: {
      section: MAINILA_SECTION,
      words: MAINILA_WORDS,
      terms: { de: 'inszenierte', sv: 'skotten vid Mainila', en: 'reported' },
      chip: 'partly the same',
    },
    dead: { ...DEAD, differs: ['de', 'en', 'uk'] },
    enFlip: {
      before: '2009-08-01',
      after: '2010-01-01',
      beforeText: 'the Soviets staged the shelling of Mainila',
      afterText: 'a border incident was reported',
      comment: 'rewrote the mainila incident part',
    },
    ruDropped: { text: RU_CLAUSE, date: '9 Jul 2014', oldid: 63917953, alive: 'de: partly the same' },
    fiScale: true,
  },
}
